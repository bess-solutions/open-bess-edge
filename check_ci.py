import urllib.request, json, sys

sys.stdout.reconfigure(encoding='utf-8')

RUN_ID = "22236041920"
REPO = "bess-solutions/open-bess-edge"

# Get jobs
url = f"https://api.github.com/repos/{REPO}/actions/runs/{RUN_ID}/jobs"
req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "check-ci"})
with urllib.request.urlopen(req) as r:
    jobs = json.load(r)

# Find failed jobs and get their log URLs
for job in jobs["jobs"]:
    if job["conclusion"] == "failure":
        print(f"\n=== FAILED JOB: {job['name']} (id={job['id']}) ===")
        # Get logs URL
        logs_url = f"https://api.github.com/repos/{REPO}/actions/jobs/{job['id']}/logs"
        req2 = urllib.request.Request(logs_url, headers={"Accept": "application/vnd.github+json", "User-Agent": "check-ci"})
        try:
            with urllib.request.urlopen(req2) as r2:
                logs = r2.read().decode('utf-8', errors='replace')
                # Print last 3000 chars
                print(logs[-3000:])
        except Exception as e:
            print(f"Could not get logs: {e}")
