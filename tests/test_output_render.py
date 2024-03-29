import os
import pathlib
from unittest import mock
from operator import attrgetter
import json

import attr
import pytest
import yaml
from click.testing import CliRunner
from jenkins_job_manager.cli import jjm

HERE = os.path.dirname(os.path.realpath(__file__))


class FakeJenkins:
    """a fake class to substitute jenkins api in these tests"""

    _url = "https://127.0.0.1/fakejenkins"
    _username = "fake"
    _password = "alsofake"

    def __init__(self, views=None, jobs=None):
        self.views: list = views or []
        self.jobs: list = jobs or []

    def ini_conf(self):
        return f"""\
[jenkins]
url = {self._url}
username = {self._username}
password = {self._password}
"""

    def get_whoami(self):
        return {"id": self._username}

    def get_plugins(self):
        return {}

    def get_views(self):
        return (
            {
                "name": d["name"],
                "url": f"{self._url}/view/{d['name']}",
                "_class": d.get("class") or "hudson.View.Something",
            }
            for d in self.views
        )

    def get_view_config(self, name):
        for d in self.views:
            if d["name"] == name:
                return d["xml"]
        return None

    def get_all_jobs(self):
        return (
            {
                "fullname": d["name"],
                "url": f"{self._url}/job/{d['name']}",
                "_class": d.get("class") or "jenkins.job.FreeStyleOrSomething",
            }
            for d in self.jobs
        )

    def get_job_config(self, name):
        for d in self.jobs:
            if d["name"] == name:
                return d["xml"]
        return None


@attr.s(slots=True, frozen=True)
class JCase:
    """quick test case schema for the yaml docs"""

    name: str = attr.ib()
    local: str = attr.ib()
    remote: dict = attr.ib()
    output_default: str = attr.ib()
    output_struct: list = attr.ib()


def _test_cases():
    with open(f"{HERE}/test_output_render.yml") as fp:
        test_cases = yaml.safe_load_all(fp)
        for test_case in filter(bool, test_cases):
            yield JCase(**test_case)


@pytest.mark.parametrize(
    "test_case", _test_cases(), ids=map(attrgetter("name"), _test_cases())
)
def test_jjm_default_plan_output(test_case: JCase):
    fake_jenkins = FakeJenkins(**test_case.remote)
    mfj = mock.patch("jenkins_job_manager.core.JenkinsJobManager.jenkins", fake_jenkins)
    runner = CliRunner()

    with mfj, runner.isolated_filesystem():
        pathlib.Path("./jjm.ini").write_text(fake_jenkins.ini_conf())
        pathlib.Path("./job.yml").write_text(test_case.local)

        # check default output
        result = runner.invoke(jjm, ["plan", "--skip-pager"], catch_exceptions=False)
        # print(result.output)
        assert result.output == test_case.output_default
        return_code = 0 if test_case.output_default == "No changes.\n" else 2
        assert result.exit_code == return_code

        # check yaml output
        result = runner.invoke(jjm, ["plan", "--output=yaml"], catch_exceptions=False)
        # print(result.output)
        assert yaml.safe_load(result.output) == test_case.output_struct
        return_code = 0 if test_case.output_struct == [] else 2
        assert result.exit_code == return_code

        # # check json output
        result = runner.invoke(jjm, ["plan", "--output=json"], catch_exceptions=False)
        # print(result.output)
        assert json.loads(result.output) == test_case.output_struct
        return_code = 0 if test_case.output_struct == [] else 2
        assert result.exit_code == return_code
