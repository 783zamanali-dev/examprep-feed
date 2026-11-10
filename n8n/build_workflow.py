"""Builds examprep-daily-news.json (the file you import into n8n) from the code in code/.
Run it again after editing any file in code/:   python build_workflow.py"""
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
js = lambda name: (HERE / "code" / name).read_text(encoding="utf-8")
UA = {"name": "User-Agent", "value": "ExamPrepFeedReader/1.0 (RSS reader)"}


def node(name, kind, version, x, params, **extra):
    return {"parameters": params, "name": name, "type": "n8n-nodes-base." + kind, "typeVersion": version,
            "position": [x, 300], "id": name.lower().replace(" ", "-").replace(":", ""), **extra}


def claude(name, x):
    return node(name, "httpRequest", 4.2, x, {
        "method": "POST", "url": "https://api.anthropic.com/v1/messages",
        "authentication": "predefinedCredentialType", "nodeCredentialType": "anthropicApi",
        "sendHeaders": True, "headerParameters": {"parameters": [
            {"name": "anthropic-version", "value": "2026-10-21"},
            {"name": "anthropic-beta", "value": "server-side-fallback-2026-07-01"}]},
        "sendBody": True, "specifyBody": "json", "jsonBody": "={{ JSON.stringify($json.request) }}",
        "options": {"timeout": 600000}}, retryOnFail=True, maxTries=3, waitBetweenTries=5000)


nodes = [
    node("Every morning", "scheduleTrigger", 1.2, 0,
         {"rule": {"interval": [{"field": "cronExpression", "expression": "0 4 * * *"}]}}),
    node("Config", "code", 2, 220, {"jsCode": js("1-config.js")}),
    node("Feeds", "code", 2, 440, {"jsCode": "// One item per feed, so the next node fetches them one by one.\n"
                                             "return $input.first().json.feeds.map(f => ({ json: f }));"}),
    node("Fetch feed", "httpRequest", 4.2, 660, {
        "url": "={{ $json.url }}", "sendHeaders": True, "headerParameters": {"parameters": [UA]},
        "options": {"timeout": 30000, "response": {"response": {"responseFormat": "text"}}}},
         onError="continueRegularOutput", retryOnFail=True, maxTries=2),
    node("Candidates", "code", 2, 880, {"jsCode": js("2-candidates.js")}),
    claude("Claude: choose stories", 1100),
    node("Write request", "code", 2, 1320, {"jsCode": js("3-write-request.js")}),
    claude("Claude: write the day", 1540),
    node("Day pack", "code", 2, 1760, {"jsCode": js("4-day-pack.js")}),
    node("Save to GitHub", "httpRequest", 4.2, 1980, {
        "method": "PUT",
        "url": "=https://api.github.com/repos/{{ $('Config').first().json.owner }}/{{ $('Config').first().json.repo }}/contents/inbox/{{ $json.file }}",
        "authentication": "predefinedCredentialType", "nodeCredentialType": "githubApi",
        "sendHeaders": True, "headerParameters": {"parameters": [{"name": "Accept", "value": "application/vnd.github+json"}]},
        "sendBody": True, "specifyBody": "json", "jsonBody": "={{ JSON.stringify($json.github) }}", "options": {}}),
]
order = [n["name"] for n in nodes]
workflow = {
    "name": "ExamPrep — daily news, summary and MCQs",
    "nodes": nodes,
    "connections": {a: {"main": [[{"node": b, "type": "main", "index": 0}]]} for a, b in zip(order, order[1:])},
    "settings": {"executionOrder": "v1", "timezone": "Asia/Karachi"},
    "active": False,
}
(HERE / "examprep-daily-news.json").write_text(json.dumps(workflow, indent=2, ensure_ascii=False), encoding="utf-8")
print("Wrote examprep-daily-news.json:", len(nodes), "nodes")
