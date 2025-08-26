# tools/sanitize_questions.py
import json, os, re, sys
from pathlib import Path
META_PATTERNS = [
    r"\s*\((?:[A-Za-zÄÖÜäöüß .+-]*#\s*\d+)\)\s*",
    r"\b(?:Allgemeinwissen|Bonus|Kategorie|Trivia)\s*#\s*\d+:?\s*"
]
def strip_meta(t): 
    s=t
    for p in META_PATTERNS: s=re.sub(p,"",s)
    s=re.sub(r"^Welche Aussage trifft zu\??$","Welche Aussage ist richtig?",s).strip()
    return re.sub(r"\s{2,}"," ",s)

root = Path(sys.argv[1] if len(sys.argv)>1 else "data")
count=0
for p in root.glob("q*.json"):
    try:
        j=json.loads(p.read_text(encoding="utf-8"))
        q=j.get("question","")
        q2=strip_meta(q)
        if q2!=q:
            j["question"]=q2
            p.write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding="utf-8")
            count+=1
    except Exception as e:
        print("skip", p.name, e)
print("geändert:", count)
