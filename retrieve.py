import subprocess
import argparse
import re
import pandas as pd
from tqdm import tqdm
import asyncio
import aiohttp
import traceback
import simplejson as json
import base64
from collections import defaultdict
import shutil

parser = argparse.ArgumentParser()
parser.add_argument(
    "-t",
    "--github_access_token",
    help="GitHub access token to overcome API rate limitations",
)
parser.add_argument(
    "-i", "--input", help="Filepath of input .csv file containing repo data"
)
parser.add_argument(
    "-o",
    "--output",
    help="Filepath of output .csv file containing information of retrieved files data",
)
parser.add_argument("-s", "--semaphore", type=int, default=5)
args = parser.parse_args()

INPUT, GITHUB_ACCESS_TOKEN = args.input, args.github_access_token


def get_file_url(repo_url: str, sha: str, module_path: str, fqn: str):
    fqn_path = re.sub("\\.", "/", fqn)
    fqn_file = re.sub("\\/[^\\/]*$", ".java", fqn_path)
    if type(module_path) != str or module_path == ".":
        return repo_url + "/blob/" + sha + "/src/test/java/" + fqn_file
    else:
        return (
            repo_url + "/blob/" + sha + "/" + module_path + "/src/test/java/" + fqn_file
        )


def make_api_pr_url(pr_url: str):
    pattern = r"https://github.com/(.+?)/(.+?)/pull/(.+?)$"
    match = re.search(pattern, pr_url)
    if match == None:
        return None
    owner, repo, pr_number = match.groups()
    url = "https://api.github.com/repos/{0}/{1}/pulls/{2}/files"
    return url.format(owner, repo, pr_number)


async def get_list_of_pr_files(
    pr_url: str, token: str, session: aiohttp.ClientSession, sem: asyncio.Semaphore
):
    if pr_url != None:
        url = make_api_pr_url(pr_url)
    else:
        return None
    headers = {"Authorization": f"token {token}"}
    async with sem:
        async with session.get(url, headers=headers) as res:
            result = await res.json()
            return result


async def get_content(
    content_url: str, token: str, session: aiohttp.ClientSession, sem: asyncio.Semaphore
):
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {token}",
    }
    async with sem:
        async with session.get(content_url, headers=headers) as res:
            result = json.loads(await res.text())
            decoded_result = base64.b64decode(result["content"]).decode("utf-8")
            return decoded_result


async def get_diff(
    pr_url: str,
    files,
    token: str,
    session: aiohttp.ClientSession,
    sem: asyncio.Semaphore,
):
    list_of_pr_files = await get_list_of_pr_files(pr_url, token, session, sem)
    content_list = []
    for i, pr_files in enumerate(list_of_pr_files):
        filepath = pr_files["filename"]
        filename = path_to_file_name(filepath)
        for file in files:
            if filename == file["testfile"]:
                content = {}
                content["idx"] = file["idx"]
                content["name"] = filename
                content["content"] = await get_content(
                    pr_files["contents_url"], token, session, sem
                )
                content["patch"] = pr_files["patch"]
                content_list.append(content)
    return content_list


def path_to_file_name(path: str):
    pattern = r"^.+/([^/]+?)$"
    result = re.match(pattern, path)
    return f"{result.group(1)}"
    # return re.sub(r"/",".",path)


def get_fully_qualified_file_name(fqn: str):
    if re.search("::", fqn) != None:
        pattern = r"(^.+/[^/\\]+)\.py(.*)$"
        result = re.match(pattern, fqn)
        try:
            return f"{result.group(1)}{result.group(2)}.py".replace("/", ".")
        except:
            return None
    else:
        pattern = r"^(.+)$"
        result = re.match(pattern, fqn)
        try:
            return f"{result.group(1)}.java"
        except:
            return None


def get_test_file_name(fqn: str):
    if re.search("::", fqn) != None:
        pattern = r"^.+/([^/\\]+\.py).*$"
        result = re.match(pattern, fqn)
        try:
            return result.group(1)
        except:
            return None
    else:
        pattern = r"^(.+\.)?([^\.]+)\.[^\.]*$"
        result = re.match(pattern, fqn)
        try:
            return f"{result.group(2)}.java"
        except:
            return None


def get_test_method_name(fqn: str):
    parsedNames = fqn.split(".")
    return parsedNames[-1]


def add_end_of_newline(code: str):
    return code + "\n"


async def main():
    df = pd.read_csv(INPUT)
    prlinks = df.PRLink.values
    testfiles = (
        df.FullyQualifiedTestName
        if "FullyQualifiedTestName" in df
        else df.PytestTestName if "PytestTestName" in df else None
    )
    df["filename"] = testfiles.map(lambda x: get_test_file_name(x))
    filenames = df["filename"].values
    df["fqfilename"] = testfiles.map(lambda x: get_fully_qualified_file_name(x))
    fqfilenames = df["fqfilename"].values
    urls = set()
    tasks = []
    verified_idxes = []
    files = defaultdict(list[str])
    sem = asyncio.Semaphore(args.semaphore)
    async with aiohttp.ClientSession() as session:
        for idx in range(df.shape[0]):
            url = prlinks[idx]
            testfile = filenames[idx]
            if testfile == None:
                continue
            urls.add(url)
            files[url].append({"testfile": testfile, "idx": idx})
        for url in urls:
            tasks.append(get_diff(url, files[url], GITHUB_ACCESS_TOKEN, session, sem))
        for f in tqdm(asyncio.as_completed(tasks), total=len(tasks)):
            try:
                results = await f
                for i, result in enumerate(results):
                    idx = result["idx"]
                    filename = fqfilenames[idx]
                    with open(f"./.files/{filename}", mode="w") as f:
                        f.write((result["content"]))
                    shutil.copy(f"./.files/{filename}", f"./.orig/{filename}")
                    with open(f"./.patches/{filename}.patch", mode="w") as f:
                        f.write(add_end_of_newline(result["patch"]))
                    subprocess.run(
                        [
                            "patch",
                            "-R",
                            f"./.files/{filename}",
                            f"./.patches/{filename}.patch",
                        ]
                    )
                    verified_idxes.append(idx)
            except:
                traceback.print_exc()
    # verified_df = df[df.index.isin(verified_idxes)]
    # verified_df.to_csv(args.output)


if __name__ == "__main__":
    asyncio.run(main())
