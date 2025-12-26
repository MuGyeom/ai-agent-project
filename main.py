import argparse, json, src.common.config as config
from src.search.main import crawl_and_classify


def run():
    parser = argparse.ArgumentParser(
        description="Crawl a URL and classify HTML content"
    )
    parser.add_argument("--url", "-u", help="Target URL to crawl")
    parser.add_argument("--json", action="store_true", help="Output result as JSON")
    args = parser.parse_args()

    url = args.url
    if not url:
        url = input("크롤링할 URL을 입력하세요: ")
    headers = config.ALTERNATE_USER_AGENT
    if not headers:
        headers = None
    else:
        headers = {"User-Agent": headers}

    result = crawl_and_classify(url, headers=headers)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result)


if __name__ == "__main__":
    run()
