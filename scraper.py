#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GOLAZO 26 — collecteur de données.
Tourne dans GitHub Actions (internet ouvert) :
1. Wikipédia (wikitext brut) -> tous les matchs + buteurs/minutes
2. API Dailymotion (beIN SPORTS France, L'Équipe) -> résumé vidéo par match
Sortie : data.json
"""
import json, re, sys, unicodedata, urllib.request, urllib.parse, datetime

UA = {"User-Agent": "golazo26-bot/1.0 (projet perso; contact via github ben99992)"}

DEBUG=[]
def get(url):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8")

def get_wikitext(title):
    url=("https://en.wikipedia.org/w/api.php?action=parse&prop=wikitext&format=json"
         "&formatversion=2&redirects=1&page="+urllib.parse.quote(title))
    j=json.loads(get(url))
    if "error" in j: raise RuntimeError(j["error"].get("info","api error"))
    return j["parse"]["wikitext"]

# ---------------- équipes : code FIFA -> (nom FR, drapeau) ----------------
TEAMS = {
"ALG":("Algérie","🇩🇿"),"ARG":("Argentine","🇦🇷"),"AUS":("Australie","🇦🇺"),"AUT":("Autriche","🇦🇹"),
"BEL":("Belgique","🇧🇪"),"BIH":("Bosnie-Herzégovine","🇧🇦"),"BRA":("Brésil","🇧🇷"),"CAN":("Canada","🇨🇦"),
"CPV":("Cap-Vert","🇨🇻"),"COL":("Colombie","🇨🇴"),"CIV":("Côte d'Ivoire","🇨🇮"),"CRO":("Croatie","🇭🇷"),
"CUW":("Curaçao","🇨🇼"),"ECU":("Équateur","🇪🇨"),"EGY":("Égypte","🇪🇬"),"ENG":("Angleterre","🏴󠁧󠁢󠁥󠁮󠁧󠁿"),
"ESP":("Espagne","🇪🇸"),"FRA":("France","🇫🇷"),"GER":("Allemagne","🇩🇪"),"GHA":("Ghana","🇬🇭"),
"HAI":("Haïti","🇭🇹"),"IRN":("Iran","🇮🇷"),"IRQ":("Irak","🇮🇶"),"ITA":("Italie","🇮🇹"),
"JPN":("Japon","🇯🇵"),"JOR":("Jordanie","🇯🇴"),"KOR":("Corée du Sud","🇰🇷"),"KSA":("Arabie saoudite","🇸🇦"),
"MAR":("Maroc","🇲🇦"),"MEX":("Mexique","🇲🇽"),"NED":("Pays-Bas","🇳🇱"),"NZL":("Nouvelle-Zélande","🇳🇿"),
"NOR":("Norvège","🇳🇴"),"PAN":("Panama","🇵🇦"),"PAR":("Paraguay","🇵🇾"),"POR":("Portugal","🇵🇹"),
"QAT":("Qatar","🇶🇦"),"COD":("RD Congo","🇨🇩"),"RSA":("Afrique du Sud","🇿🇦"),"SCO":("Écosse","🏴󠁧󠁢󠁳󠁣󠁴󠁿"),
"SEN":("Sénégal","🇸🇳"),"SUI":("Suisse","🇨🇭"),"SWE":("Suède","🇸🇪"),"TUN":("Tunisie","🇹🇳"),
"UZB":("Ouzbékistan","🇺🇿"),"USA":("États-Unis","🇺🇸"),"URU":("Uruguay","🇺🇾"),"JAM":("Jamaïque","🇯🇲"),
}
MONTHS={"January":1,"February":2,"March":3,"April":4,"May":5,"June":6,"July":7,"August":8,"September":9,"October":10,"November":11,"December":12}

def norm(s):
    s=unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c)!="Mn")

def clean_wiki(s):
    s=re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", s)       # [[a|b]] -> b
    s=re.sub(r"\{\{lang\|[^|}]*\|([^}]*)\}\}", r"\1", s)
    s=re.sub(r"<[^>]+>", "", s)
    return s.strip()

def parse_goals(block, team):
    """'[[Kylian Mbappé|Mbappé]] {{goal|66}}{{goal|90+6}}' -> liste de buts"""
    goals=[]
    if not block: return goals
    block=re.sub(r"<br\s*/?>", "\n", block)
    for line in re.split(r"[\n]", block):
        line=line.strip()
        if not line: continue
        # nom du joueur = texte avant le premier {{goal
        head=line.split("{{goal",1)[0]
        player=clean_wiki(head).strip(" ,;·")
        for g in re.finditer(r"\{\{goal\|([^}|]*)(?:\|([^}]*))?\}\}", line):
            minute=g.group(1).strip().replace("'","")
            extra=(g.group(2) or "").lower()
            gtype=""
            if "pen" in extra: gtype="pen"
            elif "o.g" in extra or "og" in extra: gtype="og"
            if player:
                goals.append({"team":team,"player":player,"minute":minute,"type":gtype})
    return goals

def parse_page(title, stage, group=None):
    """parse tous les {{footballbox}} d'une page wikipédia"""
    wikitext=get_wikitext(title)
    out=[]
    for m in re.finditer(r"\{\{football box\b(.*?)\n\}\}", wikitext, re.S|re.I):
        b=m.group(1)
        def field(name):
            f=re.search(r"\|\s*"+name+r"\s*=\s*(.*?)(?=\n\s*\||\Z)", b, re.S)
            return f.group(1).strip() if f else ""
        t1=re.search(r"\{\{fb(?:-rt)?\|(\w{3})", field("team1"))
        t2=re.search(r"\{\{fb(?:-rt)?\|(\w{3})", field("team2"))
        if not t1 or not t2: continue
        c1,c2=t1.group(1).upper(), t2.group(1).upper()
        score=field("score")
        sc=re.search(r"(\d+)\s*[–-]\s*(\d+)", score)
        aet = "a.e.t" in score.lower() or "aet" in score.lower()
        pens=""
        pn=re.search(r"\|\s*penalties\s*=", b)
        date=field("date")
        d=re.search(r"(\d{1,2})\s+([A-Z][a-z]+)\s+(\d{4})", date)
        iso=""
        if d and d.group(2) in MONTHS:
            iso="%04d-%02d-%02d"%(int(d.group(3)),MONTHS[d.group(2)],int(d.group(1)))
        stadium=clean_wiki(field("stadium"))
        stparts=[p.strip() for p in stadium.split(",")]
        stad=stparts[0] if stparts else ""
        city=stparts[1] if len(stparts)>1 else ""
        goals=parse_goals(field("goals1"),"H")+parse_goals(field("goals2"),"A")
        goals.sort(key=lambda g:(int(re.match(r"(\d+)",g["minute"]).group(1)) if re.match(r"\d",g["minute"] or "") else 999))
        n1,f1=TEAMS.get(c1,(c1,"🏳️")); n2,f2=TEAMS.get(c2,(c2,"🏳️"))
        mid="m-%s-%s-%s"%(iso or "x",c1,c2)
        for i,g in enumerate(goals):
            g["id"]="g-%s-%d"%(mid,i)
        out.append({"id":mid,"n":None,"stage":stage,"group":group or "","date":iso,"city":city,"stadium":stad,
            "home":{"code":c1,"name":n1,"flag":f1},"away":{"code":c2,"name":n2,"flag":f2},
            "sh":int(sc.group(1)) if sc else None,"sa":int(sc.group(2)) if sc else None,
            "status":"fini" if sc else "avenir","info":("après prolongation" if aet else ""),
            "goals":goals,"videos":[]})
    return out

def collect_matches():
    matches=[]
    for letter in "ABCDEFGHIJKL":
        try:
            matches+=parse_page("2026_FIFA_World_Cup_Group_"+letter,"GRP",letter)
            print("groupe",letter,"ok")
        except Exception as e:
            DEBUG.append("groupe %s: %r"%(letter,e))
    try:
        ko=parse_page("2026_FIFA_World_Cup_knockout_stage","KO")
        # phase à élimination : déduire le tour d'après la date
        for m in ko:
            d=m["date"]
            if d>= "2026-07-14": m["stage"]="F" if d>="2026-07-18" else "SF"
            elif d>="2026-07-09": m["stage"]="QF"
            elif d>="2026-07-03": m["stage"]="R16"
            else: m["stage"]="R32"
        matches+=ko
        print("knockout ok:",len(ko))
    except Exception as e:
        DEBUG.append("knockout: %r"%(e,))
    return matches

# ---------------- vidéos Dailymotion ----------------
def dm_videos(user, query):
    vids=[]
    for page in (1,2,3,4):
        url=("https://api.dailymotion.com/user/%s/videos?fields=id,title,created_time"
             "&sort=recent&limit=100&page=%d&search=%s"%(user,page,urllib.parse.quote(query)))
        try:
            j=json.loads(get(url))
        except Exception as e:
            DEBUG.append("dm %s p%d: %r"%(user,page,e)); break
        vids+=j.get("list",[])
        if not j.get("has_more"): break
    return vids

ALIASES={"FRA":["france","bleus"],"ENG":["angleterre"],"GER":["allemagne"],"NED":["pays-bas","neerlandais"],
"USA":["etats-unis","americains"],"CIV":["cote d'ivoire","ivoiriens"],"KSA":["arabie saoudite"],
"KOR":["coree du sud","coreens"],"NZL":["nouvelle-zelande"],"RSA":["afrique du sud"],"COD":["rd congo","congo"],
"CPV":["cap-vert"],"UZB":["ouzbekistan"]}
def team_tokens(code):
    name=TEAMS[code][0]
    toks=[norm(name)]
    toks+=ALIASES.get(code,[])
    return toks

def attach_videos(matches):
    pool=[]
    for user,label in (("beinsports-FR","beIN SPORTS"),("lequipe","L'Équipe")):
        for v in dm_videos(user,"Coupe du monde"):
            pool.append({"id":v["id"],"title":v["title"],"t":v.get("created_time",0),"label":label,"n":norm(v["title"])})
    print("vidéos dailymotion récupérées:",len(pool))
    resume_pat=re.compile(r"resume|le film|revivez|elimin|qualifi|s'impose|domine|renverse|arrache|festival|roule|assomme|corrige|surclasse")
    for m in matches:
        if m["status"]!="fini": continue
        toks_h=team_tokens(m["home"]["code"]); toks_a=team_tokens(m["away"]["code"])
        try: mt=datetime.datetime.fromisoformat(m["date"]).timestamp() if m["date"] else 0
        except Exception: mt=0
        best=None
        for v in pool:
            if not any(t in v["n"] for t in toks_h): continue
            if not any(t in v["n"] for t in toks_a): continue
            if mt and not (mt-3600*12 <= v["t"] <= mt+3600*72): continue
            score=(2 if resume_pat.search(v["n"]) else 0)+(1 if "mi-temps" not in v["n"] else -2)
            if best is None or score>best[0]: best=(score,v)
        if best:
            v=best[1]
            m["videos"].append({"kind":"dm","id":v["id"],"label":v["label"],"title":v["title"]})
    return matches

def main():
    matches=collect_matches()
    matches=attach_videos(matches)
    nb_g=sum(len(m["goals"]) for m in matches)
    nb_v=sum(1 for m in matches if m["videos"])
    fini=sum(1 for m in matches if m["status"]=="fini")
    data={"updated":datetime.datetime.utcnow().isoformat()+"Z",
          "stats":{"matches":len(matches),"goals":nb_g,"videos":nb_v,"finis":fini,"debug":DEBUG[:20]},
          "matches":matches}
    with open("data.json","w",encoding="utf-8") as f:
        json.dump(data,f,ensure_ascii=False,separators=(",",":"))
    print("RESUME: %d matchs, %d buts, %d vidéos, %d terminés"%(len(matches),nb_g,nb_v,fini))

if __name__=="__main__":
    main()
