from pathlib import Path
import json,math
from PIL import Image,ImageOps,ImageDraw,ImageStat
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_optimization_v1');L=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')/P.name
items=[];thumbs=[]
for f in sorted((P/'figures').glob('*.png')):
 im=Image.open(f).convert('RGB');variance=sum(ImageStat.Stat(im).var);assert im.width>=900 and im.height>=500 and variance>100,'EMPTY_OR_TOO_SMALL:'+f.name;items.append(dict(file=f.name,width=im.width,height=im.height,pixel_variance_sum=variance))
 tile=Image.new('RGB',(560,450),'white');preview=ImageOps.contain(im,(550,415));tile.paste(preview,((560-preview.width)//2,25));ImageDraw.Draw(tile).text((5,5),f.name,fill='black');thumbs.append(tile)
canvas=Image.new('RGB',(1120,450*math.ceil(len(thumbs)/2)),'#dddddd')
for i,tile in enumerate(thumbs):canvas.paste(tile,((i%2)*560,(i//2)*450))
(L/'figures').mkdir(exist_ok=True);canvas.save(L/'figures/QA_contact_sheet.png');(P/'VISUAL_QA.json').write_text(json.dumps(dict(status='AUTOMATED_PIXEL_QA_PASS',figures=items,human_agent_visual_inspection='contact sheet exported for model review; final inspection recorded separately'),indent=2));print('FIGURE_PIXEL_QA_PASS',len(items))
