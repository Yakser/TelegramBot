import copy
import datetime
from abc import ABC, abstractmethod
from pathlib import Path
import pprint
from subprocess import run

import click
import requests
import yaml
from cachier import cachier
from loguru import logger
from packaging.version import parse
from plumbum import local
from rex import rex

from updater import git_check, plumbum_msg


class Config:

    STATE_FILES_UPDATED = "FILES_UPDATED"
    STATE_TEST_RUN = "TEST_RUN"
    STATE_CONFIG_SAVED = "CONFIG_SAVED"
    STATE_COMMITED_CHANGES = "COMMITED_CHANGES"
    STATE_UPDATE_STARTED = "UPDATE_STARTED"
    STATE_UPDATE_SKIPPED = "UPDATE_SKIPPED"
    STATE_UPDATE_DONE = "UPDATE_DONE"

    def __init__(self, components_yaml_file=None):
        self.components = []
        self.config_file = components_yaml_file
        if self.config_file:
            if not self.config_file.is_file():
                logger.error(
                    "Config file %s exists but it is not file." % str(self.config_file)
                )
            self.project_dir = self.config_file.parent
        else:
            self.project_dir = None
        self.test_command = None
        self.test_dir = None
        self.git_commit = True
        self.status = {}

    def update_status(self, component, step):
        if component.component_name not in self.status:
            self.status[component.component_name] = {}
        comp = self.status[component.component_name]
        if step in [self.STATE_UPDATE_STARTED, self.STATE_UPDATE_SKIPPED]:
            message = (
                step
                + " for "
                + component.component_name
                + " in version "
                + component.current_version_tag
            )
        elif step in [self.STATE_UPDATE_DONE]:
            message = (
                step
                + " for "
                + component.component_name
                + " in version "
                + component.next_version_tag
            )
        else:
            message = step
        comp[str(datetime.datetime.now())] = message

    def get_status(self):
        return pprint.pformat(self.status, indent=4)

    def add(self, component):
        self.components.append(component)
        return self.components.index(self.components[-1])

    def components_to_dict(self):
        return {
            component.component_name: component.to_dict()
            for component in self.components
        }

    def save_to_yaml(self, file=None):
        file_to_save = Path(file) if file is not None else self.config_file
        yaml.dump(self.components_to_dict(), open(file_to_save, "w"))

    def save_config(self, destination_file=None, dry_run=False, print_yaml=False):
        if not dry_run:
            if destination_file:
                self.save_to_yaml(destination_file)
            elif self.config_file:
                self.save_to_yaml()

        if print_yaml:
            click.echo(pprint.pformat(yaml.dump(self.components_to_dict()), indent=4))

    def read_from_yaml(self, file=None):
        read_file = file or self.config_file
        self.components = []

        components_dict = (
            yaml.safe_load(open(read_file)) if read_file and read_file.is_file() else {}
        )

        for component_name in components_dict:
            compd = components_dict[component_name]
            params = {
                "component_type": compd["component-type"],
                "component_name": component_name,
                "current_version_tag": compd["current-version"],
                "repo_name": compd.get("docker-repo", Component.DEFAULT_REPO),
            }
            last_index = self.add(factory.get(**params))
            comp = self.components[last_index]
            comp.repo_name = compd.get("docker-repo", comp.DEFAULT_REPO)
            comp.prefix = compd.get("prefix", comp.DEFAULT_PREFIX)
            comp.filter = compd.get("filter", comp.DEFAULT_FILTER)
            comp.files = compd.get("files", comp.DEFAULT_FILES)
            comp.exclude_versions = compd.get(
                "exclude-versions", comp.DEFAULT_EXLUDE_VERSIONS
            )
            comp.version_pattern = compd.get(
                "version-pattern", comp.DEFAULT_VERSION_PATTERN
            )

    def count_components_to_update(self):
        self.check()
        return sum(
            [1 for component in self.components if component.newer_version_exists()]
        )

    def check(self):
        return [(comp.component_name, comp.check()) for comp in self.components]

    def run_tests(self, processed_component):
        ret = run(self.test_command, cwd=(self.test_dir or self.project_dir))
        assert ret.returncode == 0, (
            click.style("Error!", fg="red")
            + "( "
            + processed_component.component_name
            + " ) "
            + str(ret)
        )

    def commit_changes(self, component, from_version, to_version, dry_run):
        git = local["git"]
        with local.cwd(self.config_file.parent):
            ret = git_check(git["diff", "--name-only"].run(retcode=None))
            changed_files = ret[1].splitlines()
            assert set(component.files).issubset(
                set(changed_files)
            ), "Not all SRC files are in git changed files.\n" + plumbum_msg(ret)
            if not dry_run:
                git_check(git["add", self.config_file.name].run(retcode=None))
                for file_name in component.files:
                    git_check(git["add", file_name].run(retcode=None))
                commit_message = (
                    f"{component.component_name} "
                    f"updated from: {from_version} to: {to_version}"
                )
                git_check(
                    git["commit", f"--message=%s" % commit_message].run(retcode=None)
                )

    # TODO move code for updating single component outside to new methods
    def update_files(self, dry_run=False):
        counter = 0
        for component in self.components:
            if component.newer_version_exists():
                orig_current_tag = component.current_version_tag
                orig_next_tag = component.next_version_tag
                self.update_status(component, self.STATE_UPDATE_STARTED)
                counter += component.update_files(self.project_dir, dry_run)
                self.update_status(component, self.STATE_FILES_UPDATED)
                if self.test_command:
                    self.run_tests(component)
                    self.update_status(component, self.STATE_TEST_RUN)

                if not dry_run:
                    component.current_version = copy.deepcopy(component.next_version)
                    component.current_version_tag = copy.deepcopy(
                        component.next_version_tag
                    )
                self.save_config(dry_run=dry_run)
                self.update_status(component, self.STATE_CONFIG_SAVED)

                if self.git_commit:
                    self.commit_changes(
                        component, orig_current_tag, orig_next_tag, dry_run
                    )
                    self.update_status(component, self.STATE_COMMITED_CHANGES)
                self.update_status(component, self.STATE_UPDATE_DONE)
            else:
                self.update_status(component, self.STATE_UPDATE_SKIPPED)

        return counter

    def get_versions_info(self):
        new = [
            c.component_name
            + " - current: "
            + c.current_version_tag
            + " next: "
            + (click.style(c.next_version_tag, fg="green"))
            for c in self.components
            if c.newer_version_exists()
        ]
        new.sort()
        return new


class Component(ABC):

    DEFAULT_PREFIX = None
    DEFAULT_FILTER = "/.*/"
    DEFAULT_FILES = None
    DEFAULT_EXLUDE_VERSIONS = []
    DEFAULT_REPO = None
    LATEST_TAGS = ["latest"]
    DEFAULT_VERSION_PATTERN = "{version}"

    def __init__(self, component_name, current_version_tag):
        self.component_type = None
        self.component_name = component_name
        self.current_version_tag = current_version_tag
        self.current_version = parse(current_version_tag)
        self.version_tags = []
        self.next_version = self.current_version
        self.next_version_tag = self.current_version_tag
        self.prefix = self.DEFAULT_PREFIX
        self.filter = self.DEFAULT_FILTER
        self.files = self.DEFAULT_FILES
        self.exclude_versions = self.DEFAULT_EXLUDE_VERSIONS
        self.version_pattern = self.DEFAULT_VERSION_PATTERN
        super().__init__()

    def newer_version_exists(self):
        if self.current_version_tag in self.LATEST_TAGS:
            return False
        else:
            return self.next_version > self.current_version

    @abstractmethod
    def fetch_versions():
        """ should return a list of versions eg.: ('1.0.1', '2.0.2') """

    # TODO move max statement after self.next_version= to new mehtod: get_max_version_number()
    def check(self):
        if self.current_version_tag not in self.LATEST_TAGS:
            self.version_tags = self.fetch_versions()

            self.next_version = max(
                [
                    parse(tag)
                    for tag in self.version_tags
                    if (tag == rex(self.filter)) and tag not in self.exclude_versions
                ]
            )
            self.next_version_tag = (self.prefix or "") + str(self.next_version)

        return self.newer_version_exists()

    def to_dict(self):
        ret = {
            "component-type": self.component_type,
            "current-version": self.current_version_tag,
            "next-version": self.next_version_tag,
        }

        if self.prefix != self.DEFAULT_PREFIX:
            ret["prefix"] = self.prefix
        if self.filter != self.DEFAULT_FILTER:
            ret["filter"] = self.filter
        if self.files != self.DEFAULT_FILES:
            ret["files"] = self.files
        if self.exclude_versions != self.DEFAULT_EXLUDE_VERSIONS:
            ret["exclude-versions"] = self.exclude_versions
        if self.version_pattern != self.DEFAULT_VERSION_PATTERN:
            ret["version-pattern"] = self.version_pattern
        return ret

    def name_version_tag(self, version_tag):
        d = {"version": version_tag, "component": self.component_name}
        return self.version_pattern.format(**d)

    def count_occurence(self, string_to_search):
        return string_to_search.count(self.name_version_tag(self.current_version_tag))

    def replace(self, string_to_replace):
        return string_to_replace.replace(
            self.name_version_tag(self.current_version_tag),
            self.name_version_tag(self.next_version_tag),
        )

    def update_files(self, base_dir, dry_run=False):
        counter = 0

        for file_name in self.files:
            file = Path(Path(base_dir) / file_name)
            orig_content = file.read_text()
            assert self.count_occurence(orig_content) <= 1, (
                "To many verison of %s occurence in %s!"
                % (self.current_version_tag, orig_content)
            )
            if not dry_run:
                new_content = self.replace(orig_content)
                assert new_content != orig_content, (
                    "Error in version replacment for %s: no replacement done for current_version"
                    % self.component_name
                    + ": %s and next_version: %s\nOrigin\n%s\nNew\n%s."
                    % (
                        self.name_version_tag(self.current_version_tag),
                        self.name_version_tag(self.next_version_tag),
                        orig_content,
                        new_content,
                    )
                )
                file.write_text(new_content)
            counter += 1
        return counter


# TODO mark as deprecated
def clear_docker_images_cache():
    clear_versions_cache()


def clear_versions_cache():
    fetch_docker_images_versions.clear_cache()
    fetch_pypi_versions.clear_cache()


@cachier(stale_after=datetime.timedelta(days=3))
def fetch_docker_images_versions(repo_name, component_name, token_url=None):
    logger.info(repo_name + ":" + component_name + " - NOT CACHED")
    payload = {
        "service": "registry.docker.io",
        "scope": "repository:{repo}/{image}:pull".format(
            repo=repo_name, image=component_name
        ),
    }
    token_url = token_url or DockerImageComponent.TOKEN_URL
    r = requests.get(token_url, params=payload)
    if not r.status_code == 200:
        print("Error status {}".format(r.status_code))
        raise Exception("Could not get auth token")

    j = r.json()
    token = j["token"]
    h = {"Authorization": "Bearer {}".format(token)}
    r = requests.get(
        "https://index.docker.io/v2/{}/{}/tags/list".format(repo_name, component_name),
        headers=h,
    )
    return r.json().get("tags", [])


@cachier(stale_after=datetime.timedelta(days=3))
def fetch_pypi_versions(component_name):
    r = requests.get("https://pypi.org/pypi/{}/json".format(component_name))
    # it returns 404 if there is no such a package
    if not r.status_code == 200:
        return list()
    else:
        return list(r.json().get("releases", {}).keys())


class DockerImageComponent(Component):

    DEFAULT_VERSION_PATTERN = "{component}:{version}"
    TOKEN_URL = "https://auth.docker.io/token"

    def __init__(self, repo_name, component_name, current_version_tag):
        super(DockerImageComponent, self).__init__(component_name, current_version_tag)
        self.repo_name = repo_name
        self.component_type = "docker-image"
        self.version_pattern = self.DEFAULT_VERSION_PATTERN

    def fetch_versions(self):
        return fetch_docker_images_versions(self.repo_name, self.component_name)

    def to_dict(self):
        ret = super(DockerImageComponent, self).to_dict()
        ret["docker-repo"] = self.repo_name
        return ret


class PypiComponent(Component):

    DEFAULT_VERSION_PATTERN = "{component}=={version}"

    def __init__(self, component_name, current_version_tag, **_ignored):
        super(PypiComponent, self).__init__(component_name, current_version_tag)
        self.component_type = "pypi"
        self.version_pattern = self.DEFAULT_VERSION_PATTERN

    def fetch_versions(self):
        return fetch_pypi_versions(self.component_name)


class ComponentFactory:
    def get(self, component_type, **args):
        if component_type == "docker-image":
            return DockerImageComponent(**args)
        elif component_type == "pypi":
            return PypiComponent(**args)
        else:
            raise ValueError("Componet type: " + component_type + " :not implemented!")


factory = ComponentFactory()
