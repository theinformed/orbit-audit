#!/usr/bin/env python3
"""Parse an already-downloaded ESA GEO classification report, offline only."""
import argparse
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.eol_policy_probe import digest

URL='https://astronomer.ru/data/0128/Classification_of_Geosynchronous_Objects_I21R0.pdf'
DISPOSALS_2018={
    '1995-016A','1995-073A','1998-006A','1998-014A','1998-033A','1998-063A',
    '2000-012A','2000-019A','2000-038A','2000-046B','2002-040A','2002-043A',
    '2003-043A','2003-052A','1996-063B','2006-038A',
}


def parse(text,minimum=1000):
    records={}
    for page_num,page in enumerate(text.split('\f'),1):
        lines=page.splitlines()
        for pos,line in enumerate(lines):
            # Some two-letter debris designators touch the capitalized name in
            # pdftotext output (1968-081AJTranstage); preserve those nine rows.
            m=re.match(r'^(C1|C2|C4|D|L1|L2|L3|I|Ind)\.(\d+)[a-z]*\s+(\d{4}-\d{3}[A-Z]+?)(?:\s+|(?=[A-Z][a-z]))(.+)',line)
            if not m:continue
            # Descriptive names can wrap across lines; find the data-source line.
            for q in range(pos+1,min(pos+5,len(lines)-1)):
                source=lines[q].split()
                if not source or source[0] not in ('TLEs','vimpel','KIAM'):continue
                if source[0]!='TLEs':break
                values=lines[q+1].split()
                if len(values)<8 or values[1]!='TEME' or not values[0].isdigit():break
                norad=int(values[0]);a,e=float(values[2]),float(values[3])
                if norad in records:raise ValueError(f'Duplicate ESA TLE record {norad}')
                date=re.search(r'\d{4}-\d{2}-\d{2}',lines[q])
                records[norad]=dict(norad=norad,classification=m[1],cospar=m[3],
                    nameAndType=m[4].strip(),page=page_num,source='TLEs',referenceDate='2019-01-01',
                    orbitEpoch=date.group() if date else None,semiMajorAxisKm=a,eccentricity=e,
                    inclinationDeg=float(values[4]),perigeeAboveGeoKm=a*(1-e)-42164,
                    listed2018Disposal=m[3] in DISPOSALS_2018,url=URL)
                break
    if len(records)<minimum:raise ValueError(f'Incomplete ESA extraction: {len(records)}')
    return records


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pdf',type=Path,required=True)
    p.add_argument('--text',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    records=parse(a.text.read_text())
    result=dict(pdfSha256=digest(a.pdf),textSha256=digest(a.text),url=URL,objects=records)
    with a.output.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(dict(records=len(records),disposals2018=sum(r['listed2018Disposal'] for r in records.values()))))


if __name__=='__main__':main()
