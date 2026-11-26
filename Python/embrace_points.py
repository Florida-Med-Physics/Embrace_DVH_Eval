"""Reference points in the supplied EMBRACE worksheet's order."""
# key, label, physical-dose template row, alpha/beta
POINTS = (
    ('point_a_left','Point A LT',31,10),
    ('point_a_right','Point A RT',33,10),
    ('vaginal_left','Vaginal LT',93,3),
    ('vaginal_right','Vaginal RT',95,3),
    ('rectovaginal','Rectal',65,3),
    ('bladder_point','Bladder',57,3),
    ('vaginal','Vaginal point (unspecified)',None,None),
)
REFERENCE_KEYS=tuple(key for key,_,row,_ in POINTS if row is not None)


def suggest_point(name, group=''):
    """Conservative name matching; suggestions are always reviewed before import."""
    import re
    from difflib import SequenceMatcher
    def norm(s):
        s=re.sub(r'\blef\b','left',s.lower())
        s=re.sub(r'\brigh\b','right',s)
        s=re.sub(r'(?:fx|fraction)[ _-]*\d+$','',s.lower()).strip()
        return re.sub(r'[^a-z0-9+-]','',s)
    n=norm(name)
    aliases={
        'point_a_left':['al','aleft','pointal','pointaleft','leftpointa','lefta'],
        'point_a_right':['ar','aright','pointar','pointaright','rightpointa','righta'],
        'bladder_point':['bladderpoint','bladderreferencepoint','icrubladder'],
        'rectovaginal':['rectovaginal','rectovaginalpoint','rectovaginalreferencepoint','rvpoint','rectalpoint','rectumpoint','rectalreferencepoint'],
        'vaginal_left':['vagina5mmleft','vaginal5mmleft','5mmleft','vaginalpointleft','vaginalleft','vaginalpointl','vaginall'],
        'vaginal_right':['vagina5mmright','vaginal5mmright','5mmright','vaginalpointright','vaginalright','vaginalpointr','vaginalr'],
        'vaginal':['vaginalpoint','vaginapoint'],
    }
    group_name=norm(group)
    if group_name in ('vaginalpoints','vaginalpoint','vaginapoints') and n in ('l','left','r','right'):
        return 'vaginal_left' if n in ('l','left') else 'vaginal_right'
    # A dash is punctuation except for the signed PIBS offsets.
    if not n.startswith('pibs'): n=n.replace('-','').replace('+','')
    for key,values in aliases.items():
        if n in values:return key
    if n in ('l','left','r','right') and norm(group) in ('apoints','pointa','pointaset'):
        return 'point_a_left' if n in ('l','left') else 'point_a_right'
    # Short identifiers, unsigned/ambiguous PIBS offsets and numbered points
    # cannot be resolved safely by edit distance.
    if len(n)<8 or 'pibs' in n or re.fullmatch(r'p\d+',n):return None
    scores=[]
    for key,values in aliases.items():
        if key.startswith('point_a_'):
            side='left' if key.endswith('left') else 'right'
            if side not in n:continue
        if key in ('vaginal_left','vaginal_right'):
            if ('left' if key.endswith('left') else 'right') not in n:continue
        if key.startswith('pibs'):continue
        scores.append((max(SequenceMatcher(None,n,a).ratio() for a in values if len(a)>=5),key))
    scores.sort(reverse=True)
    a_scores=[score for score in scores if score[1].startswith('point_a_')]
    if a_scores and a_scores[0][0]>=.9 and (len(scores)==1 or all(a_scores[0][0]-score>=.08 for score,key in scores if key!=a_scores[0][1])):
        return a_scores[0][1]
    return scores[0][1] if scores and scores[0][0]>=.9 and (len(scores)==1 or scores[0][0]-scores[1][0]>=.08) else None
