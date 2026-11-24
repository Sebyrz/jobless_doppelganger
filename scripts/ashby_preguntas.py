#!/usr/bin/env python3
"""Preguntas del formulario de un aviso de Ashby (API pública no documentada del sitio). Sin cuenta.
    python3 ashby_preguntas.py <tablero> <job_id> [...]
"""
import json, sys, urllib.request
Q = '''query ApiJobPosting($organizationHostedJobsPageName: String!, $jobPostingId: String!) { jobPosting(organizationHostedJobsPageName: $organizationHostedJobsPageName, jobPostingId: $jobPostingId) { title applicationForm { sections { fieldEntries { ... on FormFieldEntry { isRequired field } } } } } }'''


def preguntas(tablero, jid):
    body = json.dumps({"operationName": "ApiJobPosting", "variables": {"organizationHostedJobsPageName": tablero, "jobPostingId": jid}, "query": Q}).encode()
    req = urllib.request.Request("https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobPosting", data=body,
                                 headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    d = json.loads(urllib.request.urlopen(req, timeout=20).read())
    jp = d["data"]["jobPosting"] or {}
    out = []
    for s in (jp.get("applicationForm") or {}).get("sections", []):
        for f in s["fieldEntries"]:
            fl = f.get("field") or {}
            out.append({"label": fl.get("title"), "required": f.get("isRequired"), "type": fl.get("type"),
                        "opciones": [o.get("label") for o in (fl.get("selectableValues") or [])]})
    return jp.get("title"), out


if __name__ == "__main__":
    args = sys.argv[1:]
    for t, j in zip(args[::2], args[1::2]):
        title, qs = preguntas(t, j)
        print(f"\n== {t} | {title}")
        for q in qs:
            print("  ", "*" if q["required"] else " ", (q["label"] or "")[:120], "|", q["type"], "|", q["opciones"][:6])
