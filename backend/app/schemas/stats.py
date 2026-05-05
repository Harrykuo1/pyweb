from pydantic import BaseModel


class StatsResponse(BaseModel):
    total_members: int
    total_jobs: int
    # Distinct count of Job.company across the whole table — drives the
    # "涵蓋 N 間公司" stat on the home dashboard.
    total_companies: int
    # Recruitment-year span (MIN / MAX of Job.job_year). Both are None
    # when the jobs table is empty so the frontend can fall back to a
    # placeholder rather than showing "0 - 0".
    year_min: int | None
    year_max: int | None
