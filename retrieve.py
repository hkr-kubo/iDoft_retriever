import os
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

parser = argparse.ArgumentParser()
parser.add_argument('-t', '--github_access_token', help='GitHub access token to overcome API rate limitations')
parser.add_argument('-i', '--input', help='Filepath of input .csv file containing repo data')
parser.add_argument('-o', '--output', help='Filepath of output .json file containing information of modified files')
parser.add_argument('-s', '--semaphore',type=int)
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
    headers = {"Authorization": f"token {token}"}
    async with sem:
        async with session.get(url,headers=headers) as res:
            result =  await res.json()
            return url,result

async def main():
    df = pd.read_csv(INPUT)
    prlink = df.PRLink.values
    urls = set()
    tasks = []
    sem = asyncio.Semaphore(args.semaphore)
    async with aiohttp.ClientSession() as session:
        for idx in range(df.shape[0]):
            url = prlink[idx]
            if type(url) != float:
                urls.add(url)
        for url in urls:
            tasks.append(get_list_of_pr_files(url,GITHUB_ACCESS_TOKEN,session,sem))
        for f in tqdm(asyncio.as_completed(tasks,timeout=60.0),total=len(tasks)):
            try:
                result = await f                    
                if result != None:
                    with open("./files/test.json",mode="w") as f:
                        json.dump(result,f)
            except:
                traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(main())