from typing import List, Union
from urllib.parse import urljoin

from aiohttp import ClientSession
from bs4 import BeautifulSoup
from fastapi import HTTPException
from fastapi import status as http_status

async def get_html(url: str) -> BeautifulSoup:
    async with ClientSession() as session:
        async with session.get(url) as response:
            text = await response.text()

            if response.status == 200:
                html = BeautifulSoup(markup=text, features="lxml")

                return html

    raise HTTPException(status_code=http_status.HTTP_501_NOT_IMPLEMENTED,
                        detail=f"Scraper didn't succeed in getting data:\n"
                               f"\turl: {url}\n"
                               f"\tstatus code: {response.status}\n"
                               f"\tresponse text: {text}")
    
    
    