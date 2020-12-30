from ovos_utils.log import LOG
from ovos_utils.json_helper import merge_dict
from ovos_skills_manager.github import *
from ovos_skills_manager.licenses import get_license_type, is_viral, \
    is_permissive
from ovos_skills_manager.utils import desktop_to_json, readme_to_json
from ovos_skills_manager.requirements import validate_manifest
import base64
import json
from enum import Enum


class GithubAPI(str, Enum):
    BASE = "https://api.github.com"
    LICENSE_LIST = BASE + "/licenses"
    LICENSE_DATA = LICENSE_LIST + "/{license_type}"
    REPO = BASE + "/repos/{owner}/{repo}"
    REPO_LICENSE = REPO + "/license"
    REPO_RELEASES = REPO + "/tags"
    REPO_FILE = REPO + '/contents/{file}'


# Github API methods
def repo_data_from_api(url, branch=None):
    author, repo = author_repo_from_github_url(url)
    url = GithubAPI.REPO.format(owner=author, repo=repo)
    try:
        return requests.get(url).json()
    except Exception as e:
        raise GithubAPIRepoNotFound


def license_data_from_api(url, branch=None):
    author, repo = author_repo_from_github_url(url)
    url = GithubAPI.REPO_LICENSE.format(owner=author, repo=repo)
    try:
        return requests.get(url).json()
    except Exception as e:
        pass
    raise GithubAPILicenseNotFound


def repo_releases_from_api(url, branch=None):
    try:
        author, repo = author_repo_from_github_url(url)
        url = GithubAPI.REPO_RELEASES.format(owner=author, repo=repo)
        return requests.get(url).json()
    except Exception as e:
        raise GithubAPIReleasesNotFound(str(e))


# url getters
def get_license_url_from_api(url, branch=None):
    try:
        data = license_data_from_api(url, branch)
        return data["download_url"]
    except GithubAPILicenseNotFound:
        pass
    for dst in GITHUB_LICENSE_FILES:
        try:
            data = get_file_from_api(url, dst)
        except GithubAPIFileNotFound:
            continue
        return data["download_url"]
    raise GithubAPILicenseNotFound


# data getters
def get_branch_from_github_url(url):
    try:
        api_data = repo_data_from_api(url)
        return api_data['default_branch']
    except Exception as e:
        raise GithubAPIInvalidBranch(str(e))


def get_latest_release_from_api(url):
    return repo_releases_from_api(url)[0]


def get_file_from_api(url, filepath):
    author, repo = author_repo_from_github_url(url)
    url = GithubAPI.REPO_FILE.format(owner=author, repo=repo, file=filepath)
    data = requests.get(url).json()
    if data.get("message", "") != 'Not Found':
        return data
    raise GithubAPIFileNotFound


def get_readme_from_api(url):
    for dst in GITHUB_README_FILES:
        try:
            data = get_file_from_api(url, dst)
        except GithubAPIFileNotFound:
            continue
        readme = data["content"]
        if data["encoding"] == "base64":
            return base64.b64decode(readme).decode("utf-8")
        return readme
    raise GithubAPIReadmeNotFound


def get_license_type_from_api(url, branch=None):
    try:
        data = repo_data_from_api(url, branch)
        return data["license"]["key"]
    except Exception as e:
        pass
    text = get_license_from_api(url, branch)
    return get_license_type(text)


def get_license_from_api(url, branch=None):
    try:
        data = license_data_from_api(url, branch)
        text = data["content"]
        if data["encoding"] == "base64":
            return base64.b64decode(text).decode("utf-8")
        return text
    except Exception as e:
        pass
    for dst in GITHUB_LICENSE_FILES:
        data = get_file_from_api(url, dst)
        text = data["content"]
        if data["encoding"] == "base64":
            return base64.b64decode(text).decode("utf-8")
        return text
    raise GithubAPILicenseNotFound


def get_requirements_from_api(url, branch=None):
    author, repo = author_repo_from_github_url(url)
    content = None
    for dst in GITHUB_REQUIREMENTS_FILES:
        try:
            data = get_file_from_api(url, dst.format(repo=repo))
        except GithubAPIFileNotFound:
            continue
        content = data["content"]
        if data["encoding"] == "base64":
            content = base64.b64decode(content).decode("utf-8")
    if not content:
        raise GithubAPIFileNotFound
    return [t for t in content.split("\n")
            if t.strip() and not t.strip().startswith("#")]


def get_skill_requirements_from_api(url, branch=None):
    author, repo = author_repo_from_github_url(url)
    content = None
    for dst in GITHUB_SKILL_REQUIREMENTS_FILES:
        try:
            data = get_file_from_api(url, dst.format(repo=repo))
        except GithubAPIFileNotFound:
            continue
        content = data["content"]
        if data["encoding"] == "base64":
            content = base64.b64decode(content).decode("utf-8")
    if not content:
        raise GithubAPIFileNotFound
    return [t for t in content.split("\n")
            if t.strip() and not t.strip().startswith("#")]


def get_manifest_from_api(url):
    author, repo = author_repo_from_github_url(url)
    content = None
    for dst in GITHUB_MANIFEST_FILES:
        try:
            data = get_file_from_api(url, dst.format(repo=repo))
        except GithubAPIFileNotFound:
            continue
        content = data["content"]
        if data["encoding"] == "base64":
            content = base64.b64decode(content).decode("utf-8")
    if not content:
        raise GithubAPIFileNotFound
    return validate_manifest(content)


def get_json_from_api(url, branch=None):
    author, repo = author_repo_from_github_url(url)
    for dst in GITHUB_JSON_FILES:
        try:
            data = get_file_from_api(url, dst.format(repo=repo))
        except GithubAPIFileNotFound:
            continue
        content = data["content"]
        if data["encoding"] == "base64":
            json_data = base64.b64decode(content).decode("utf-8")
        else:
            json_data = content
        return json.loads(json_data)
    raise GithubAPIFileNotFound


def get_desktop_from_api(url, branch=None):
    author, repo = author_repo_from_github_url(url)
    for dst in GITHUB_DESKTOP_FILES:
        try:
            data = get_file_from_api(url, dst.format(repo=repo))
        except GithubAPIFileNotFound:
            continue
        readme = data["content"]
        if data["encoding"] == "base64":
            return base64.b64decode(readme).decode("utf-8")
        return readme
    raise GithubAPIFileNotFound


# data parsers
def get_readme_json_from_api(url):
    readme = get_readme_from_api(url)
    return readme_to_json(readme)


def get_desktop_json_from_api(url, branch=None):
    desktop = get_desktop_from_api(url, branch)
    return desktop_to_json(desktop)


def get_requirements_json_from_api(url, branch=None):
    data = {"python": [], "system": {}, "skill": []}
    try:
        manif = get_manifest_from_api(url)
        data = manif['dependencies'] or {"python": [], "system": {},
                                         "skill": []}
    except GithubAPIFileNotFound:
        pass
    try:
        req = get_requirements_from_api(url, branch)
        data["python"] = list(set(data["python"] + req))
    except GithubAPIFileNotFound:
        pass
    try:
        skill_req = get_skill_requirements_from_api(url, branch)
        data["skill"] = list(set(data["skill"] + skill_req))
    except GithubAPIFileNotFound:
        pass
    return data


def get_skill_from_api(url, branch=None, strict=False):
    data = {}
    try:
        api_data = repo_data_from_api(url, branch)
        data["branch"] = branch = api_data['default_branch']
        data["short_description"] = api_data['description']
        data["license"] = api_data["license"]["key"]
        data["foldername"] = api_data["name"]
        data["last_updated"] = api_data['updated_at']
        data["url"] = api_data["html_url"]
        data["authorname"] = api_data["owner"]["login"]
    except GithubAPIException as e:
        LOG.error("Failed to retrieve repo data from github api")
        raise GithubAPIException(e)

    try:
        releases = repo_releases_from_api(url, branch)
        if branch:
            for r in releases:
                if r["name"] == branch or r["commit"]["sha"] == branch:
                    data["version"] = r["name"]
                    data["download_url"] = r["tarball_url"]
                    break
        else:
            data["version"] = releases[0]["name"]
            data["download_url"] = releases[0]["tarball_url"]
    except GithubAPIException as e:
        LOG.error("Failed to retrieve releases data from github api")
        if strict:
            raise GithubAPIReleasesNotFound

    # augment with readme data
    try:
        data = merge_dict(data, get_readme_json_from_api(url),
                          merge_lists=True, skip_empty=True, no_dupes=True)
    except GithubAPIReadmeNotFound:
        pass

    data["requirements"] = get_requirements_json_from_api(url, branch)

    # augment tags
    if "tags" not in data:
        data["tags"] = []
    if is_viral(data["license"]):
        data["tags"].append("viral-license")
    elif is_permissive(data["license"]):
        data["tags"].append("permissive-license")
    elif "unknown" in data["license"]:
        data["tags"].append("no-license")

    return data


print(get_skill_from_api("https://github.com/AIIX/youtube-skill"))