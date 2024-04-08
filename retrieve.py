import os
import subprocess
import argparse
import re
import math
import numpy as np
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
parser.add_argument('-t', '--github_access_token', help='GitHub access token to overcome API rate limitations')
parser.add_argument('-i', '--input', help='Filepath of input .csv file containing repo data')
parser.add_argument('-o', '--output', help='Filepath of output .json file containing information of modified files')
parser.add_argument('-s', '--semaphore',type=int,default=5)
args = parser.parse_args()

INPUT, GITHUB_ACCESS_TOKEN = args.input, args.github_access_token

def get_file_url(repo_url:str,sha:str,module_path:str,fqn:str):
    fqn_path = re.sub("\\.","/",fqn)
    fqn_file = re.sub("\\/[^\\/]*$",".java",fqn_path)
    if type(module_path) != str or module_path == ".":
        return repo_url + "/blob/" + sha + "/src/test/java/" + fqn_file
    else:
        return repo_url + "/blob/" + sha + "/" + module_path + "/src/test/java/" + fqn_file

def make_api_pr_url(pr_url:str):
    pattern = r'https://github.com/(.+?)/(.+?)/pull/(.+?)$'
    match = re.search(pattern, pr_url)
    if match == None:
        return None
    owner, repo, pr_number = match.groups()
    url=("https://api.github.com/repos/{:0}/{:1}/pulls/{:2}/files")
    return url.format(owner, repo, pr_number)

async def get_list_of_pr_files(pr_url:str,token:str,session:aiohttp.ClientSession,sem:asyncio.Semaphore):
    if pr_url != None:
        url = make_api_pr_url(pr_url)
    else:
        return None
    headers = {"Authorization": f"token {token}"}
    async with sem:
        async with session.get(url,headers=headers) as res:
            result = await res.json()
            return result
        
async def get_content(content_url:str,token:str,session:aiohttp.ClientSession,sem:asyncio.Semaphore):
    headers = {"Accept": "application/vnd.github.v3+json", "Authorization": f"token {token}"}
    async with sem:
        async with session.get(content_url,headers=headers) as res:
            result = json.loads(await res.text())
            decoded_result = base64.b64decode(result["content"]).decode("utf-8")
            return decoded_result
        
async def get_diff(pr_url:str,files:list,token:str,session:aiohttp.ClientSession,sem:asyncio.Semaphore):
    list_of_pr_files = await get_list_of_pr_files(pr_url,token,session,sem)
    #print(list_of_pr_files)
    content_list = []
    for i,pr_files in enumerate(list_of_pr_files):
        filepath = pr_files["filename"]
        filename = path_to_file_name(filepath)
        print(filename,files)
        if filename in files:
            content = {}
            content["name"] = filename
            content["content"] = await get_content(pr_files["contents_url"],token,session,sem)
            content["patch"] = pr_files["patch"]
            content_list.append(content)
    return content_list

def path_to_file_name(path:str):
    pattern=r"^.+/([^/]+?)$"
    result = re.match(pattern,path)
    return f"{result.group(1)}"

def get_test_file_name(fqn:str):
    if re.search("::",fqn) != None:
        pattern=r"^.+/([^/]+\.py).*$"
        result = re.match(pattern,fqn)
        try:
            return result.group(1)
        except:
            print(fqn)
            return None
    else:
        pattern=r"^(.+\.)?([^\.]+)\.[^\.]*$"
        result = re.match(pattern,fqn)
        try:
            return f"{result.group(2)}.java"
        except:
            print(fqn)
            return None

async def main():
    df = pd.read_csv(INPUT)
    prlinks = df.PRLink.values
    testfiles = df.FullyQualifiedTestName.values if "FullyQualifiedTestName" in df else df.PytestTestName.values if "PytestTestName" in df else None
    urls = set()
    tasks = []
    files = defaultdict(list[str])
    sem = asyncio.Semaphore(args.semaphore)
    async with aiohttp.ClientSession() as session:
        for idx in range(df.shape[0]):
            url = prlinks[idx]
            testfile = get_test_file_name(testfiles[idx])
            if testfile == None:
                continue
            if type(url) != float:
                urls.add(url)
                files[url].append(testfile)
        for url in urls:
            tasks.append(get_diff(url,files[url],GITHUB_ACCESS_TOKEN,session,sem))
        for f in tqdm(asyncio.as_completed(tasks),total=len(tasks)):
            try:
                results = await f 
                for i,result in enumerate(results):
                    with open(f"./.files/{result["name"]}",mode="w") as f:
                        f.write(result["content"])
                    shutil.copy(f"./.files/{result["name"]}",f"./.files/{result["name"]}.orig")    
                    with open(f"./.patches/{result["name"]}.patch",mode="w") as f:
                        f.write(result["patch"])
                    subprocess.run(["patch","-R",f"./.files/{result["name"]}",f"./.patches/{result["name"]}.patch"])#TODO
            except:
                traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(main())