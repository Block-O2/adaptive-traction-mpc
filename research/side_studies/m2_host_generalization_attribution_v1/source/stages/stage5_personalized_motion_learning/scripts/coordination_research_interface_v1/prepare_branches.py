from common import *
src=S/'src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime_coordination_v1.py'
text=src.read_text();needle='            coordination_interface.boundary(locals())\n        reference_state = '
new='''            coordination_interface.boundary(locals())
            if getattr(coordination_interface, 'branch_output_dir', None) is not None:
                output_dir = coordination_interface.branch_output_dir
        reference_state = '''
assert text.count(needle)==1;text=text.replace(needle,new);src.write_text(text);(P/'runtime_coordination_v1.py').write_text(text)
for file in W.glob('*.py'):shutil.copy2(file,P/file.name)
save('REPAIRS.json',dict(repairs=[dict(id=1,error='generated module resource root',fix='new importable versioned module at native package path'),dict(id=2,error='spawn worker cannot import dynamically named module',fix='normal versioned package import'),dict(id=3,error='dataclass serialization and matching absent-value masks',fix='explicit asdict and NaN-mask equality; no physical criteria changed')],scientific_changes=0))
print('branch runtime prepared')
