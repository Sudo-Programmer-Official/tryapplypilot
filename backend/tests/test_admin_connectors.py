from __future__ import annotations

import os
import sys
import types
import unittest
from unittest.mock import patch

if "asyncpg" not in sys.modules:
    asyncpg_stub = types.ModuleType("asyncpg")
    asyncpg_stub.Connection = object
    asyncpg_stub.Record = dict
    asyncpg_stub.connect = None
    sys.modules["asyncpg"] = asyncpg_stub

if "jwt" not in sys.modules:
    jwt_stub = types.ModuleType("jwt")

    class _InvalidTokenError(Exception):
        pass

    jwt_stub.InvalidTokenError = _InvalidTokenError
    jwt_stub.encode = lambda payload, secret, algorithm=None: "stub-token"
    jwt_stub.decode = lambda token, secret, algorithms=None, issuer=None: {"type": "access"}
    sys.modules["jwt"] = jwt_stub

if "argon2" not in sys.modules:
    argon2_stub = types.ModuleType("argon2")
    argon2_exceptions_stub = types.ModuleType("argon2.exceptions")

    class _PasswordHasher:
        def hash(self, password: str) -> str:
            return f"hashed:{password}"

        def verify(self, hashed: str, password: str) -> bool:
            return hashed == f"hashed:{password}"

    argon2_stub.PasswordHasher = _PasswordHasher
    argon2_exceptions_stub.VerifyMismatchError = type("VerifyMismatchError", (Exception,), {})
    argon2_exceptions_stub.InvalidHashError = type("InvalidHashError", (Exception,), {})
    argon2_stub.exceptions = argon2_exceptions_stub
    sys.modules["argon2"] = argon2_stub
    sys.modules["argon2.exceptions"] = argon2_exceptions_stub

from app.config import get_settings
from app.domain import CompanyPreference
from app.services.admin_connectors import validate_company_connector


class _ValidationConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[object, ...]]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def execute(self, query: str, *args: object) -> None:
        self.executed.append((query, args))


class AdminConnectorValidationTests(unittest.IsolatedAsyncioTestCase):
    def tearDown(self) -> None:
        get_settings.cache_clear()

    async def test_validate_ashby_company_fetches_live_board_metadata(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_RUNTIME_MODE": "seed"}, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

        company = CompanyPreference(
            id="ramp",
            company="Ramp",
            enabled=True,
            tier=1,
            priority=1,
            connector="ashby",
            poll_interval_minutes=5,
            country="US",
            career_url="https://jobs.ashbyhq.com/ramp",
            external_identifier="ramp",
            role_families=["Platform Engineering"],
        )
        conn = _ValidationConnection()
        payload = {
            "jobs": [
                {
                    "id": "job-1",
                    "title": "Senior Platform Engineer",
                    "location": "New York, NY, USA",
                    "secondaryLocations": [{"location": "Remote (United States)"}],
                    "isListed": True,
                    "isRemote": True,
                    "workplaceType": "Remote",
                    "descriptionPlain": "Build backend infrastructure.",
                    "publishedAt": "2026-07-18T17:12:35.753+00:00",
                    "jobUrl": "https://jobs.ashbyhq.com/ramp/job-1",
                    "applyUrl": "https://jobs.ashbyhq.com/ramp/job-1/application",
                }
            ]
        }

        with (
            patch("app.services.admin_connectors.list_catalog_companies", return_value=[company]),
            patch("app.services.admin_connectors.connection", return_value=conn),
            patch("app.connectors.ashby.request_json", return_value=payload),
        ):
            validation = await validate_company_connector(company.id, settings)

        self.assertEqual(validation["status"], "passed")
        self.assertEqual(validation["reason"], "validated_live")
        self.assertEqual(validation["jobs_fetched"], 1)
        self.assertEqual(validation["requests_made"], 1)
        self.assertTrue(validation["inventory_complete"])
        self.assertEqual(validation["sample_job_title"], "Senior Platform Engineer")
        self.assertEqual(validation["sample_apply_url"], "https://jobs.ashbyhq.com/ramp/job-1/application")
        self.assertEqual(len(conn.executed), 1)

    async def test_validate_microsoft_company_records_partial_inventory_metadata(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_RUNTIME_MODE": "seed"}, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

        company = CompanyPreference(
            id="microsoft",
            company="Microsoft",
            enabled=True,
            tier=1,
            priority=1,
            connector="microsoft-careers",
            poll_interval_minutes=5,
            country="US",
            career_url="https://jobs.careers.microsoft.com/",
            external_identifier="microsoft.com",
            role_families=["Platform Engineering"],
        )
        conn = _ValidationConnection()
        search_payload = {
            "data": {
                "count": 25,
                "positions": [
                    {
                        "id": "job-1",
                        "displayJobId": "20001",
                        "name": "Senior Software Engineer",
                        "postedTs": 1784428800,
                        "creationTs": 1784420000,
                        "positionUrl": "/careers/job/1",
                        "workLocationOption": "remote",
                        "locationFlexibility": "0 days / week in-office – remote",
                        "department": "Software Engineering",
                        "atsJobId": "ats-1",
                        "locations": ["Seattle, WA, USA"],
                        "standardizedLocations": ["US"],
                    }
                ],
            }
        }
        detail_payload = {
            "data": {
                "jobDescription": "<p>Detailed backend platform role.</p>",
                "publicUrl": "https://careers.microsoft.com/us/en/job/1",
            }
        }

        def _request_json(*args, **kwargs):
            url = str(kwargs.get("url") or args[1])
            if "position_details" in url:
                return detail_payload
            return search_payload

        with (
            patch("app.services.admin_connectors.list_catalog_companies", return_value=[company]),
            patch("app.services.admin_connectors.connection", return_value=conn),
            patch("app.connectors.microsoft_careers.request_json", side_effect=_request_json),
        ):
            validation = await validate_company_connector(company.id, settings)

        self.assertEqual(validation["status"], "passed")
        self.assertEqual(validation["reason"], "inventory_partial")
        self.assertEqual(validation["jobs_fetched"], 1)
        self.assertEqual(validation["requests_made"], 2)
        self.assertFalse(validation["inventory_complete"])
        self.assertEqual(validation["pages_scanned"], 1)
        self.assertEqual(validation["expected_pages"], 3)
        self.assertEqual(validation["partial_reason"], "page_limit_reached")
        self.assertEqual(validation["sample_apply_url"], "https://careers.microsoft.com/us/en/job/1")
        self.assertEqual(len(conn.executed), 1)

    async def test_validate_workday_company_fetches_live_board_metadata(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_RUNTIME_MODE": "seed"}, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

        company = CompanyPreference(
            id="nvidia",
            company="NVIDIA",
            enabled=True,
            tier=2,
            priority=20,
            connector="workday",
            poll_interval_minutes=10,
            country="US",
            career_url="https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite",
            external_identifier="nvidia/NVIDIAExternalCareerSite",
            role_families=["Platform Engineering"],
        )
        conn = _ValidationConnection()

        def _request_json(*args, **kwargs):
            method = str(args[0])
            url = str(kwargs.get("url") or args[1])
            if method == "GET":
                return {
                    "jobPostingInfo": {
                        "title": "Principal Platform Engineer",
                        "jobDescription": "<p>Build distributed AI platform infrastructure.</p>",
                        "location": "Remote, United States",
                        "postedOn": "Posted Today",
                        "startDate": "2026-07-19",
                        "timeType": "Full time",
                        "externalUrl": "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/job/Remote-USA/Principal-Platform-Engineer_JR123456",
                    },
                    "jobRequisitionLocation": {
                        "descriptor": "Remote, United States",
                        "country": {"alpha2Code": "US", "descriptor": "United States"},
                    },
                }
            return {
                "total": 1,
                "jobPostings": [
                    {
                        "title": "Principal Platform Engineer",
                        "externalPath": "/job/Remote-USA/Principal-Platform-Engineer_JR123456",
                        "locationsText": "Remote, United States",
                        "postedOn": "Posted Today",
                        "bulletFields": ["JR123456"],
                    }
                ],
            }

        with (
            patch("app.services.admin_connectors.list_catalog_companies", return_value=[company]),
            patch("app.services.admin_connectors.connection", return_value=conn),
            patch("app.connectors.workday.request_json", side_effect=_request_json),
        ):
            validation = await validate_company_connector(company.id, settings)

        self.assertEqual(validation["status"], "passed")
        self.assertEqual(validation["reason"], "validated_live")
        self.assertEqual(validation["jobs_fetched"], 1)
        self.assertEqual(validation["requests_made"], 2)
        self.assertTrue(validation["inventory_complete"])
        self.assertEqual(validation["sample_job_title"], "Principal Platform Engineer")
        self.assertEqual(
            validation["sample_apply_url"],
            "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/job/Remote-USA/Principal-Platform-Engineer_JR123456",
        )
        self.assertEqual(len(conn.executed), 1)

    async def test_validate_google_company_fetches_live_page_metadata(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_RUNTIME_MODE": "seed"}, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

        company = CompanyPreference(
            id="google",
            company="Google",
            enabled=True,
            tier=2,
            priority=16,
            connector="google-careers",
            poll_interval_minutes=10,
            country="US",
            career_url="https://www.google.com/about/careers/applications/jobs/results/?hl=en_US",
            external_identifier="google",
            role_families=["Platform Engineering"],
        )
        conn = _ValidationConnection()
        html_payload = (
            "<html><body><script>AF_initDataCallback({key: 'ds:1', hash: '2', data:"
            "[[[\"job-1\",\"Senior Software Engineer, AI/ML\","
            "\"https://www.google.com/about/careers/applications/signin?jobId=job-1\","
            "[null,\"<ul><li>Build backend platforms.</li></ul>\"],"
            "[null,\"<h3>Minimum qualifications:</h3><ul><li>Python</li></ul>\"],"
            "\"projects/gweb-careers-proto/company/google\",null,\"Google\",\"en-US\","
            "[[\"Seattle, WA, USA\",[\"Seattle, WA, USA\"],\"Seattle\",\"98101\",\"WA\",\"US\"]],"
            "[null,\"Remote eligible role building distributed systems for AI workloads.\"],"
            "[2],[1784200000,0],[1784300000,0],[1784300500,0],"
            "[null,\"The application window will remain open based on business needs.\"],"
            "null,null,[null,\"Preferred working location: <b>Seattle, WA, USA</b>.\"],"
            "[null,\"<ul><li>Python</li></ul>\"],3]],null,1,1], sideChannel: {}});</script></body></html>"
        )

        with (
            patch("app.services.admin_connectors.list_catalog_companies", return_value=[company]),
            patch("app.services.admin_connectors.connection", return_value=conn),
            patch("app.connectors.google_careers.request_text", return_value=html_payload),
        ):
            validation = await validate_company_connector(company.id, settings)

        self.assertEqual(validation["status"], "passed")
        self.assertEqual(validation["reason"], "validated_live")
        self.assertEqual(validation["jobs_fetched"], 1)
        self.assertEqual(validation["requests_made"], 1)
        self.assertTrue(validation["inventory_complete"])
        self.assertEqual(validation["sample_job_title"], "Senior Software Engineer, AI/ML")
        self.assertEqual(
            validation["sample_apply_url"],
            "https://www.google.com/about/careers/applications/signin?jobId=job-1",
        )
        self.assertEqual(len(conn.executed), 1)

    async def test_validate_amazon_company_fetches_live_page_metadata(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_RUNTIME_MODE": "seed"}, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

        company = CompanyPreference(
            id="amazon",
            company="Amazon",
            enabled=True,
            tier=2,
            priority=17,
            connector="amazon-jobs",
            poll_interval_minutes=10,
            country="US",
            career_url="https://www.amazon.jobs/en/search?base_query=software+development+engineer&country=USA&sort=recent",
            external_identifier="amazon",
            role_families=["Platform Engineering"],
        )
        conn = _ValidationConnection()
        payload = {
            "hits": 1,
            "jobs": [
                {
                    "id": "uuid-10477971",
                    "id_icims": "10477971",
                    "title": "Software Development Engineer",
                    "company_name": "Amazon Development Center U.S., Inc.",
                    "country_code": "USA",
                    "description": "Build distributed systems for search infrastructure.",
                    "basic_qualifications": "- Python",
                    "preferred_qualifications": "- AI infrastructure",
                    "job_category": "Software Development",
                    "job_schedule_type": "full-time",
                    "job_path": "/en/jobs/10477971/software-development-engineer",
                    "location": "US, WA, Seattle",
                    "locations": [
                        "{\"normalizedLocation\":\"Seattle, Washington, USA\",\"location\":\"Seattle, Washington, USA\",\"countryIso2a\":\"US\",\"countryIso3a\":\"USA\",\"type\":\"REMOTE\"}"
                    ],
                    "normalized_location": "Seattle, Washington, USA",
                    "posted_date": "July 18, 2026",
                    "updated_time": "1 day",
                    "url_next_step": "https://account.amazon.jobs/jobs/10477971/apply",
                    "business_category": "aws",
                }
            ],
        }

        with (
            patch("app.services.admin_connectors.list_catalog_companies", return_value=[company]),
            patch("app.services.admin_connectors.connection", return_value=conn),
            patch("app.connectors.amazon_jobs.request_json", return_value=payload),
        ):
            validation = await validate_company_connector(company.id, settings)

        self.assertEqual(validation["status"], "passed")
        self.assertEqual(validation["reason"], "validated_live")
        self.assertEqual(validation["jobs_fetched"], 1)
        self.assertEqual(validation["requests_made"], 1)
        self.assertTrue(validation["inventory_complete"])
        self.assertEqual(validation["sample_job_title"], "Software Development Engineer")
        self.assertEqual(validation["sample_apply_url"], "https://account.amazon.jobs/jobs/10477971/apply")
        self.assertEqual(len(conn.executed), 1)

    async def test_validate_smartrecruiters_company_fetches_live_board_metadata(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_RUNTIME_MODE": "seed"}, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

        company = CompanyPreference(
            id="servicenow",
            company="ServiceNow",
            enabled=True,
            tier=2,
            priority=27,
            connector="smartrecruiters",
            poll_interval_minutes=10,
            country="US",
            career_url="https://careers.smartrecruiters.com/ServiceNow",
            external_identifier="ServiceNow",
            role_families=["Platform Engineering"],
        )
        conn = _ValidationConnection()

        def _request_json(*args, **kwargs):
            url = str(kwargs.get("url") or args[1])
            if url.endswith("/744000138497339"):
                return {
                    "id": "744000138497339",
                    "name": "Senior Platform Engineer",
                    "applyUrl": "https://jobs.smartrecruiters.com/ServiceNow/744000138497339-senior-platform-engineer?oga=true",
                    "postingUrl": "https://jobs.smartrecruiters.com/ServiceNow/744000138497339-senior-platform-engineer",
                    "jobAd": {
                        "sections": {
                            "jobDescription": {"title": "Job Description", "text": "<p>Build distributed systems.</p>"},
                            "qualifications": {"title": "Qualifications", "text": "<ul><li>Python</li></ul>"},
                        }
                    },
                }
            return {
                "offset": 0,
                "limit": 1,
                "totalFound": 1,
                "content": [
                    {
                        "id": "744000138497339",
                        "name": "Senior Platform Engineer",
                        "uuid": "uuid-744000138497339",
                        "company": {"identifier": "ServiceNow", "name": "ServiceNow"},
                        "releasedDate": "2026-07-19T10:16:34.476Z",
                        "location": {
                            "city": "Seattle",
                            "country": "us",
                            "remote": True,
                            "hybrid": False,
                            "fullLocation": "Seattle, Washington, United States",
                        },
                        "ref": "https://api.smartrecruiters.com/v1/companies/ServiceNow/postings/744000138497339",
                    }
                ],
            }

        with (
            patch("app.services.admin_connectors.list_catalog_companies", return_value=[company]),
            patch("app.services.admin_connectors.connection", return_value=conn),
            patch("app.connectors.smartrecruiters.request_json", side_effect=_request_json),
        ):
            validation = await validate_company_connector(company.id, settings)

        self.assertEqual(validation["status"], "passed")
        self.assertEqual(validation["reason"], "validated_live")
        self.assertEqual(validation["jobs_fetched"], 1)
        self.assertEqual(validation["requests_made"], 2)
        self.assertTrue(validation["inventory_complete"])
        self.assertEqual(validation["sample_job_title"], "Senior Platform Engineer")
        self.assertEqual(
            validation["sample_apply_url"],
            "https://jobs.smartrecruiters.com/ServiceNow/744000138497339-senior-platform-engineer?oga=true",
        )
        self.assertEqual(len(conn.executed), 1)

    async def test_validate_icims_company_fetches_live_board_metadata(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_RUNTIME_MODE": "seed"}, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

        company = CompanyPreference(
            id="icims",
            company="iCIMS",
            enabled=True,
            tier=3,
            priority=90,
            connector="icims",
            poll_interval_minutes=15,
            country="US",
            career_url="https://careers.icims.com/careers-home",
            external_identifier="careers.icims.com",
            role_families=["Platform Engineering"],
        )
        conn = _ValidationConnection()
        payload = {
            "count": 1,
            "totalCount": 1,
            "jobs": [
                {
                    "data": {
                        "slug": "6504",
                        "req_id": "6504",
                        "title": "Senior Platform Engineer",
                        "description": "Build distributed systems and AI platform services.",
                        "responsibilities": "<ul><li>Build backend platforms.</li></ul>",
                        "qualifications": "<ul><li>Python</li></ul>",
                        "employment_type": "FULL_TIME",
                        "location_name": "United States (Remote)",
                        "full_location": "United States",
                        "short_location": "United States",
                        "country": "United States",
                        "country_code": "US",
                        "categories": [{"name": "Engineering"}],
                        "category": [" Engineering "],
                        "tags1": ["Experienced"],
                        "tags2": ["Remote"],
                        "posted_date": "2026-07-18T15:54:00+0000",
                        "update_date": "2026-07-19T12:00:00+0000",
                        "apply_url": "https://careers-customer0.icims.com/jobs/6504/login",
                        "meta_data": {"canonical_url": "https://careers.icims.com/jobs/6504?lang=en-us"},
                    }
                }
            ],
        }

        with (
            patch("app.services.admin_connectors.list_catalog_companies", return_value=[company]),
            patch("app.services.admin_connectors.connection", return_value=conn),
            patch("app.connectors.icims.request_json", return_value=payload),
        ):
            validation = await validate_company_connector(company.id, settings)

        self.assertEqual(validation["status"], "passed")
        self.assertEqual(validation["reason"], "validated_live")
        self.assertEqual(validation["jobs_fetched"], 1)
        self.assertEqual(validation["requests_made"], 1)
        self.assertTrue(validation["inventory_complete"])
        self.assertEqual(validation["sample_job_title"], "Senior Platform Engineer")
        self.assertEqual(validation["sample_apply_url"], "https://careers-customer0.icims.com/jobs/6504/login")
        self.assertEqual(len(conn.executed), 1)

    async def test_validate_jobvite_company_fetches_live_board_metadata(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_RUNTIME_MODE": "seed"}, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

        company = CompanyPreference(
            id="progress",
            company="Progress",
            enabled=True,
            tier=3,
            priority=83,
            connector="jobvite",
            poll_interval_minutes=15,
            country="US",
            career_url="https://jobs.jobvite.com/careers/progress/jobs",
            external_identifier="progress",
            role_families=["Platform Engineering"],
        )
        conn = _ValidationConnection()
        list_html = """
        <html><body>
          <h3 class="h2">Engineering Platform</h3>
          <table class="jv-job-list"><tbody>
            <tr>
              <td class="jv-job-list-name"><a href="/progress/job/ojob123">Principal Software Engineer - Distributed Systems</a></td>
              <td class="jv-job-list-location">Remote, United States</td>
            </tr>
          </tbody></table>
        </body></html>
        """
        detail_html = """
        <html><body>
          <script type="application/ld+json">
            {
              "@context": "http://schema.org",
              "@type": "JobPosting",
              "datePosted": "2026-07-18",
              "description": "<div>Build AI platform services with Python.</div>",
              "industry": "Engineering Platform",
              "identifier": "ojob123",
              "title": "Principal Software Engineer - Distributed Systems"
            }
          </script>
          <a class="jv-button jv-button-primary jv-button-apply" href="/progress/job/ojob123/apply">Apply</a>
        </body></html>
        """

        def _request_text(*args, **kwargs):
            url = str(kwargs.get("url") or args[1])
            if url.endswith("/jobs"):
                return list_html
            return detail_html

        with (
            patch("app.services.admin_connectors.list_catalog_companies", return_value=[company]),
            patch("app.services.admin_connectors.connection", return_value=conn),
            patch("app.connectors.jobvite.request_text", side_effect=_request_text),
        ):
            validation = await validate_company_connector(company.id, settings)

        self.assertEqual(validation["status"], "passed")
        self.assertEqual(validation["reason"], "validated_live")
        self.assertEqual(validation["jobs_fetched"], 1)
        self.assertEqual(validation["requests_made"], 2)
        self.assertTrue(validation["inventory_complete"])
        self.assertEqual(validation["sample_job_title"], "Principal Software Engineer - Distributed Systems")
        self.assertEqual(validation["sample_apply_url"], "https://jobs.jobvite.com/progress/job/ojob123/apply")
        self.assertTrue(validation["sample_description_present"])
        self.assertEqual(len(conn.executed), 1)

    async def test_validate_comeet_company_fetches_live_board_metadata(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_RUNTIME_MODE": "seed"}, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

        company = CompanyPreference(
            id="comeet-sandbox",
            company="Sandbox Company",
            enabled=True,
            tier=3,
            priority=85,
            connector="comeet",
            poll_interval_minutes=15,
            country="US",
            career_url="https://www.comeet.co/careers-api/2.0/company/E5.007/positions?token=5E7236A0BCE5E7295111B55E70BCE",
            external_identifier="E5.007:5E7236A0BCE5E7295111B55E70BCE",
            role_families=["Platform Engineering"],
        )
        conn = _ValidationConnection()
        payload = [
            {
                "uid": "E8.91F",
                "name": "Senior Platform Engineer",
                "department": "Engineering",
                "workplace_type": "Remote",
                "employment_type": "Full-time",
                "experience_level": "Intermediate",
                "time_updated": "2026-07-19T16:19:06Z",
                "company_name": "Sandbox Company",
                "url_active_page": "https://www.comeet.com/jobs/sandbox/E5.007/senior-platform-engineer/E8.91F",
                "url_comeet_hosted_page": "https://www.comeet.com/jobs/sandbox/E5.007/senior-platform-engineer/E8.91F",
                "position_url": "https://www.comeet.co/careers-api/2.0/company/E5.007/positions/E8.91F?token=5E7236A0BCE5E7295111B55E70BCE",
                "location": {
                    "name": "Seattle, WA",
                    "country": "US",
                    "city": "Seattle",
                    "state": "WA",
                    "is_remote": True,
                },
                "categories": [{"name": "Team", "value": "Platform", "order": 1}],
                "details": [
                    {"name": "Description", "value": "<p>Build distributed platform services.</p>", "order": 1},
                    {"name": "Requirements", "value": "<ul><li>Python</li></ul>", "order": 2},
                ],
            }
        ]

        with (
            patch("app.services.admin_connectors.list_catalog_companies", return_value=[company]),
            patch("app.services.admin_connectors.connection", return_value=conn),
            patch("app.connectors.comeet.request_json", return_value=payload),
        ):
            validation = await validate_company_connector(company.id, settings)

        self.assertEqual(validation["status"], "passed")
        self.assertEqual(validation["reason"], "validated_live")
        self.assertEqual(validation["jobs_fetched"], 1)
        self.assertEqual(validation["requests_made"], 1)
        self.assertTrue(validation["inventory_complete"])
        self.assertEqual(validation["sample_job_title"], "Senior Platform Engineer")
        self.assertEqual(
            validation["sample_apply_url"],
            "https://www.comeet.com/jobs/sandbox/E5.007/senior-platform-engineer/E8.91F",
        )
        readiness = validation["production_readiness"]
        self.assertEqual(readiness["status"], "pending")
        readiness_by_key = {item["key"]: item for item in readiness["checks"]}
        self.assertEqual(readiness_by_key["discovery"]["status"], "passed")
        self.assertEqual(readiness_by_key["pagination"]["status"], "not_applicable")
        self.assertEqual(readiness_by_key["job_details"]["status"], "passed")
        self.assertEqual(readiness_by_key["apply_url"]["status"], "passed")
        self.assertEqual(readiness_by_key["scheduler"]["status"], "pending_evidence")
        self.assertEqual(len(conn.executed), 1)

    async def test_validate_oracle_company_fetches_live_requisition_metadata(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_RUNTIME_MODE": "seed"}, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

        company = CompanyPreference(
            id="oracle",
            company="Oracle",
            enabled=True,
            tier=2,
            priority=26,
            connector="oracle-recruiting-cloud",
            poll_interval_minutes=10,
            country="US",
            career_url="https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/jobsearch/jobs",
            external_identifier="CX_45001",
            role_families=["Platform Engineering"],
        )
        conn = _ValidationConnection()
        payload = {
            "items": [
                {
                    "TotalJobsCount": 1,
                    "requisitionList": [
                        {
                            "Id": "333254",
                            "Title": "Principal Data Center E2E Project Manager",
                            "PostedDate": "2026-07-19",
                            "PrimaryLocation": "Abilene, TX, United States",
                            "PrimaryLocationCountry": "United States",
                            "ShortDescriptionStr": "Drive OCI data center delivery.",
                            "WorkplaceType": "On-site",
                            "ExternalResponsibilitiesStr": "<p>Lead delivery execution.</p>",
                            "ExternalQualificationsStr": "<p>Experience with cloud infrastructure.</p>",
                        }
                    ],
                }
            ]
        }

        with (
            patch("app.services.admin_connectors.list_catalog_companies", return_value=[company]),
            patch("app.services.admin_connectors.connection", return_value=conn),
            patch("app.connectors.oracle_recruiting_cloud.request_json", return_value=payload),
        ):
            validation = await validate_company_connector(company.id, settings)

        self.assertEqual(validation["status"], "passed")
        self.assertEqual(validation["reason"], "validated_live")
        self.assertEqual(validation["jobs_fetched"], 1)
        self.assertEqual(validation["requests_made"], 1)
        self.assertTrue(validation["inventory_complete"])
        self.assertEqual(validation["sample_job_title"], "Principal Data Center E2E Project Manager")
        self.assertEqual(
            validation["sample_apply_url"],
            "https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/jobsearch/job/333254/",
        )
        readiness = validation["production_readiness"]
        self.assertEqual(readiness["status"], "pending")
        readiness_by_key = {item["key"]: item for item in readiness["checks"]}
        self.assertEqual(readiness_by_key["discovery"]["status"], "passed")
        self.assertEqual(readiness_by_key["pagination"]["status"], "pending_evidence")
        self.assertEqual(len(conn.executed), 1)

    async def test_validate_successfactors_company_fetches_live_job_metadata(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_RUNTIME_MODE": "seed"}, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

        company = CompanyPreference(
            id="sap",
            company="SAP",
            enabled=True,
            tier=2,
            priority=84,
            connector="successfactors",
            poll_interval_minutes=10,
            country="US",
            career_url="https://jobs.sap.com/search/?sortColumn=referencedate&sortDirection=desc",
            external_identifier="sap",
            role_families=["Platform Engineering"],
        )
        conn = _ValidationConnection()
        search_html = """
        <html><body>
        <div>Results 1 – 25 of 1 Page 1 of 1</div>
        <table id="searchresults">
          <tr>
            <td><a href="/job/Newtown-Square-SAP-NS2-AI-Consultant-Specialist/1400000001/">SAP NS2 AI Consultant Specialist</a></td>
            <td>Newtown Square, PA, US, 19073</td>
          </tr>
        </table>
        </body></html>
        """
        detail_html = """
        <html><body>
        <a href="/talentcommunity/apply/1400000001/?locale=en_US">Apply now »</a>
        <h1>SAP NS2 AI Consultant Specialist</h1>
        <div>Posted Date: Jul 19, 2026</div>
        <div>Location: Newtown Square, PA, US, 19073</div>
        <div>#LI-Hybrid Build AI consulting workflows for enterprise customers.</div>
        <div>Find similar jobs:</div>
        </body></html>
        """

        def _request_text(*args, **kwargs):
            url = str(kwargs.get("url") or args[1])
            if "/job/" in url:
                return detail_html
            return search_html

        with (
            patch("app.services.admin_connectors.list_catalog_companies", return_value=[company]),
            patch("app.services.admin_connectors.connection", return_value=conn),
            patch("app.connectors.successfactors.request_text", side_effect=_request_text),
        ):
            validation = await validate_company_connector(company.id, settings)

        self.assertEqual(validation["status"], "passed")
        self.assertEqual(validation["reason"], "validated_live")
        self.assertEqual(validation["jobs_fetched"], 1)
        self.assertEqual(validation["requests_made"], 2)
        self.assertTrue(validation["inventory_complete"])
        self.assertEqual(validation["sample_job_title"], "SAP NS2 AI Consultant Specialist")
        self.assertEqual(
            validation["sample_apply_url"],
            "https://jobs.sap.com/talentcommunity/apply/1400000001/?locale=en_US",
        )
        readiness = validation["production_readiness"]
        self.assertEqual(readiness["status"], "pending")
        readiness_by_key = {item["key"]: item for item in readiness["checks"]}
        self.assertEqual(readiness_by_key["discovery"]["status"], "passed")
        self.assertEqual(readiness_by_key["job_details"]["status"], "passed")
        self.assertEqual(readiness_by_key["apply_url"]["status"], "passed")
        self.assertEqual(len(conn.executed), 1)

    async def test_validate_bamboohr_company_is_blocked_until_public_feed_is_supported(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_RUNTIME_MODE": "seed"}, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

        company = CompanyPreference(
            id="bamboohr-test",
            company="BambooHR Example",
            enabled=True,
            tier=3,
            priority=99,
            connector="bamboohr",
            poll_interval_minutes=15,
            country="US",
            career_url="https://example.bamboohr.com/careers",
            external_identifier="example",
            role_families=["Platform Engineering"],
        )
        conn = _ValidationConnection()

        with (
            patch("app.services.admin_connectors.list_catalog_companies", return_value=[company]),
            patch("app.services.admin_connectors.connection", return_value=conn),
        ):
            validation = await validate_company_connector(company.id, settings)

        self.assertEqual(validation["status"], "failed")
        self.assertEqual(validation["reason"], "planned")
        readiness = validation["production_readiness"]
        self.assertEqual(readiness["status"], "blocked")
        readiness_by_key = {item["key"]: item for item in readiness["checks"]}
        self.assertEqual(readiness_by_key["discovery"]["status"], "blocked")
        self.assertIn("authenticated company credentials", readiness_by_key["discovery"]["detail"])
        self.assertEqual(len(conn.executed), 1)

    async def test_validate_ibm_company_is_blocked_by_public_waf_challenge(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_RUNTIME_MODE": "seed"}, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

        company = CompanyPreference(
            id="ibm-test",
            company="IBM",
            enabled=True,
            tier=1,
            priority=5,
            connector="ibm-careers",
            poll_interval_minutes=5,
            country="US",
            career_url="https://www.ibm.com/careers/search",
            external_identifier="ibm.com",
            role_families=["Platform Engineering"],
        )
        conn = _ValidationConnection()

        with (
            patch("app.services.admin_connectors.list_catalog_companies", return_value=[company]),
            patch("app.services.admin_connectors.connection", return_value=conn),
        ):
            validation = await validate_company_connector(company.id, settings)

        self.assertEqual(validation["status"], "failed")
        self.assertEqual(validation["reason"], "planned")
        readiness = validation["production_readiness"]
        self.assertEqual(readiness["status"], "blocked")
        readiness_by_key = {item["key"]: item for item in readiness["checks"]}
        self.assertEqual(readiness_by_key["discovery"]["status"], "blocked")
        self.assertIn("AWS WAF JavaScript challenge", readiness_by_key["discovery"]["detail"])
        self.assertIn("July 20, 2026", readiness_by_key["discovery"]["detail"])
        self.assertEqual(len(conn.executed), 1)


if __name__ == "__main__":
    unittest.main()
