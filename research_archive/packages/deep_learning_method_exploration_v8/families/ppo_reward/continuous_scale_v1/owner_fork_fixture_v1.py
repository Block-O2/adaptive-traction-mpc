"""Approved <=60s SYNTHETIC_ONLY AST-extracted owner/fork check.

No Beta/worker/environment module is imported. Only actual owner assignments,
assert_owner/put and GeneratorExit handler AST nodes are compiled. Synthetic
save callbacks contain no learner/policy/physics state or fake real receipts.
"""
from pathlib import Path
import argparse
import ast
import copy
from datetime import datetime
import gc
import hashlib
import json
import os
import resource
import signal
import sys
import time

sys.dont_write_bytecode=True


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def put(path,value):
    path.write_text(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+"\n")


def extract(source):
    tree=ast.parse(source.read_text(),filename=str(source))
    function=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=="sequence")
    assignments=[node for node in function.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ("owner_pid","owner_start_ticks","owner_ticks") for t in node.targets)]
    helpers=[node for node in function.body if isinstance(node,ast.FunctionDef) and node.name in ("assert_owner","put")]
    outer=next(node for node in function.body if isinstance(node,ast.Try) and any(isinstance(h.type,ast.Name) and h.type.id=="GeneratorExit" for h in node.handlers))
    handler=next(h for h in outer.handlers if isinstance(h.type,ast.Name) and h.type.id=="GeneratorExit")
    if len(assignments)!=2 or len(helpers)!=2:raise ValueError("ACTUAL_OWNER_AST_SHAPE_CHANGED")
    owner_guard=next(node for node in helpers if node.name=="assert_owner")
    if not any(isinstance(node,ast.Raise) and isinstance(node.exc,ast.Call) and isinstance(node.exc.func,ast.Name) and node.exc.func.id=="GeneratorExit" for node in ast.walk(owner_guard)):
        raise ValueError("ACTUAL_OWNER_GUARD_MUST_REJECT_CHILD_WITH_GENERATOR_EXIT")
    return assignments,helpers,handler


def compiled_fixture(source,writer,common_source):
    assignments,helpers,handler=extract(source)
    support=ast.parse('''
def save_status(stage, **extra):
    put("OWNER_CANCEL_EVIDENCE", {"stage":stage,"sentinel":sentinel,"extra":extra,"synthetic_only":True})
def save(stage):
    put("OWNER_CANCEL_EVIDENCE", {"stage":stage,"sentinel":sentinel,"synthetic_only":True})
''').body
    body=ast.parse('''
try:
    put("READY_EVIDENCE", {"stage":"SYNTHETIC_PENDING_BEFORE_FORK","sentinel":sentinel,"synthetic_only":True})
    yield put
except GeneratorExit:
    pass
''').body[0]
    body.handlers=[copy.deepcopy(handler)]
    fn=ast.FunctionDef(name="_synthetic_extracted_owner_generator",args=ast.arguments(posonlyargs=[],args=[ast.arg(arg="sentinel")],kwonlyargs=[],kw_defaults=[],defaults=[]),
        body=copy.deepcopy(assignments)+copy.deepcopy(helpers)+support+[body],decorator_list=[])
    # Beta's real put helper uses canonical(). Extract that exact pure helper as
    # well, without importing the common module or any actor dependency.
    common_ast=ast.parse(common_source.read_text())
    canonical=next(node for node in common_ast.body if isinstance(node,ast.FunctionDef) and node.name=="canonical")
    module=ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(canonical),fn],type_ignores=[]))
    namespace={"os":os,"Path":Path,"json":json,"original_put":writer,"root_put":writer}
    exec(compile(module,str(source)+"::SYNTHETIC_AST_ONLY","exec"),namespace)
    extracted=ast.dump(ast.Module(body=copy.deepcopy(assignments)+copy.deepcopy(helpers)+[copy.deepcopy(handler)],type_ignores=[]),include_attributes=False)
    return namespace["_synthetic_extracted_owner_generator"],hashlib.sha256(extracted.encode()).hexdigest(),ast.unparse(module)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--main-agent-approved-synthetic-owner-fork-60s",action="store_true")
    args=parser.parse_args()
    if not args.main_agent_approved_synthetic_owner_fork_60s:raise ValueError("EXPLICIT_MAIN_OWNER_FIXTURE_APPROVAL_REQUIRED")
    here=Path(__file__).resolve().parent;package=here.parents[2]
    binding=json.loads((here/"OWNER_FIXTURE_SOURCE_BINDING_V1.json").read_text())
    for rel,expected in binding["files_sha256"].items():
        if sha(here/rel)!=expected:raise ValueError("OWNER_FIXTURE_BOUND_SOURCE_CHANGED:"+rel)
    manifest=json.loads((here/"BETA_SOURCE_MANIFEST_V1.json").read_text())
    for rel,expected in manifest["local_files_sha256"].items():
        if sha(here/rel)!=expected:raise ValueError("BETA_FROZEN_SOURCE_CHANGED:"+rel)
    activation=json.loads((package/"ACTIVATION.json").read_text())
    deadline=datetime.fromisoformat(activation["hard_deadline_utc"]).timestamp()
    if time.time()>=deadline-60:raise ValueError("ORIGINAL_GLOBAL_DEADLINE")
    output=here/"owner_fork_fixture_v1"
    if output.exists():raise ValueError("REFUSE_OWNER_FIXTURE_OVERWRITE")
    output.mkdir()
    owner_pid=os.getpid();ticks=int(Path("/proc/self/stat").read_text().rsplit(")",1)[1].split()[19])
    start=time.time();cpu_start=time.process_time();active_child=None
    signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError("SYNTHETIC_OWNER_LOCAL_60S")))
    signal.alarm(60)
    counters={"actual_linux_forks":0,"child_GeneratorExit_close_or_GC":0,"child_direct_write_rejected_by_actual_guard":0,
              "owner_cancellations":0,"full_sequence_calls":0,"learner_initializations":0,"learner_forward":0,
              "learner_updates":0,"MuJoCo_or_environment_calls":0,"new_physics":0,"synthetic_generator_instances":0,
              "actual_extracted_put_attempts_expected":0,"actual_extracted_put_completed_expected":0}
    results=[]
    initial={"status":"STARTED_SYNTHETIC_ONLY_OWNER_AST_FORK","start_unix":start,"pid":owner_pid,"start_ticks":ticks,
             "local_deadline_unix":start+60,"original_global_deadline_unix":deadline,
             "fixture_binding_sha256":sha(here/"OWNER_FIXTURE_SOURCE_BINDING_V1.json"),
             "no_actor_modules_imported":True,"new_physics":0}
    put(output/"START.json",initial)
    try:
        for filename in ("gate1_sequence_candidate_v2.py","beta_sampling_sequence_candidate_v1.py"):
            for mode in ("explicit_close","garbage_collection"):
                label=filename.removesuffix(".py")+"_"+mode
                log=output/(label+"_SHARED_WRITES.jsonl")
                def shared_writer(relative,payload):
                    # Intentionally no fixture owner guard: if actual extracted
                    # code allowed a child write, this real file would expose it.
                    with log.open("a") as handle:
                        handle.write(json.dumps({"actual_writer_pid":os.getpid(),"relative":relative,"payload":payload},sort_keys=True,allow_nan=False)+"\n")
                        handle.flush();os.fsync(handle.fileno())
                factory,ast_sha,extracted=compiled_fixture(here/filename,shared_writer,here/"beta_sampling_common_v1.py")
                (output/(label+"_EXTRACTED_OWNER_AST.py")).write_text(extracted+"\n")
                sentinel={"schema":"SYNTHETIC_PENDING_SENTINEL_NOT_LEARNER","immutable_case":label,"values":[1,2,3],"tuple_for_canonical_fixture":(3,[4,5],None)}
                gen=factory(sentinel);writer=next(gen);counters["synthetic_generator_instances"]+=1
                before=log.read_bytes();rfd,wfd=os.pipe();child=os.fork()
                if child==0:
                    os.close(rfd)
                    try:
                        blocked=False
                        try:writer("FORBIDDEN_CHILD_SHARED_WRITE",{"synthetic_only":True})
                        except GeneratorExit:blocked=True
                        if mode=="explicit_close":gen.close()
                        else:
                            del gen
                            gc.collect()
                        os.write(wfd,json.dumps({"child_pid":os.getpid(),"direct_child_write_blocked":blocked,"close_mode":mode}).encode())
                        os.close(wfd);os._exit(0)
                    except BaseException as error:
                        os.write(wfd,json.dumps({"child_pid":os.getpid(),"error_type":type(error).__name__,"error":str(error)}).encode())
                        os.close(wfd);os._exit(2)
                active_child=child;os.close(wfd);counters["actual_linux_forks"]+=1
                report=os.read(rfd,65536);os.close(rfd)
                _,status=os.waitpid(child,0);active_child=None
                if not os.WIFEXITED(status) or os.WEXITSTATUS(status)!=0:raise AssertionError("SYNTHETIC_CHILD_FAILED:"+report.decode())
                report=json.loads(report)
                if report.get("direct_child_write_blocked") is not True:raise AssertionError("ACTUAL_OWNER_GUARD_ALLOWED_CHILD_WRITE")
                if log.read_bytes()!=before:raise AssertionError("CHILD_GENERATOR_EXIT_OR_DIRECT_CALL_WROTE_SHARED_FILE")
                counters["child_GeneratorExit_close_or_GC"]+=1;counters["child_direct_write_rejected_by_actual_guard"]+=1
                gen.close();counters["owner_cancellations"]+=1
                records=[json.loads(line) for line in log.read_text().splitlines()]
                if len(records)!=2 or any(r["actual_writer_pid"]!=owner_pid for r in records):raise AssertionError("OWNER_CANCELLATION_AUTHORITY_OR_WRITE_COUNT")
                if records[0]["relative"]!="READY_EVIDENCE" or records[1]["relative"]!="OWNER_CANCEL_EVIDENCE":raise AssertionError("OWNER_CANCEL_DID_NOT_PRESERVE_EVIDENCE")
                if digest(records[0]["payload"]["sentinel"])!=digest(sentinel) or digest(records[1]["payload"]["sentinel"])!=digest(sentinel):raise AssertionError("SYNTHETIC_PENDING_SENTINEL_MUTATED")
                counters["actual_extracted_put_attempts_expected"]+=3;counters["actual_extracted_put_completed_expected"]+=2
                results.append({"source":filename,"source_sha256":sha(here/filename),"extracted_owner_AST_sha256":ast_sha,
                    "mode":mode,"child_report_via_pipe_not_shared_file":report,"child_filesystem_writes":0,
                    "child_GeneratorExit_silent":True,"original_READY_bytes_preserved_through_child":True,
                    "owner_cancel_preserved_exact_synthetic_sentinel":True,"parent_shared_file_writes":2,
                    "actual_owner_cancel_stage":records[1]["payload"]["stage"]})
        for rel,expected in manifest["local_files_sha256"].items():
            if sha(here/rel)!=expected:raise ValueError("SOURCE_CHANGED_DURING_OWNER_FIXTURE")
        if any(name in sys.modules for name in ("beta_policy","beta_optimizer_candidate_v2","categorical_policy","mujoco")):
            raise AssertionError("LEARNER_OR_PHYSICS_MODULE_IMPORTED")
        end={**initial,"status":"PASS_SYNTHETIC_ONLY_AST_OWNER_LINUX_FORK","end_unix":time.time(),"wall_s":time.time()-start,
             "cpu_self_s":time.process_time()-cpu_start,"cpu_children_user_s":resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime,
             "cpu_children_system_s":resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime,"counters":counters,"cases":results,
             "shared_filesystem_writes_by_children":0,"shared_filesystem_writes_by_owner":8,
             "parent_GeneratorExit_handlers_executed":4,"child_GeneratorExit_handlers_executed":4,
             "child_pipe_reports":4,"full_real_generator_or_adapter_validation_claim":False,
             "actual_beta_clock_initialized":False,"all_frozen_Beta_and_Gate1_source_unchanged":True}
        put(output/"END.json",end)
        print(json.dumps({k:end[k] for k in ("status","wall_s","cpu_self_s","cpu_children_user_s","cpu_children_system_s","counters","shared_filesystem_writes_by_children","shared_filesystem_writes_by_owner")}))
    except BaseException as error:
        if os.getpid()==owner_pid:
            put(output/"FAILURE.json",{**initial,"error_type":type(error).__name__,"error":str(error),"counters":counters,
                "partial_cases":results,"all_partial_logs_retained":True,"end_unix":time.time()})
        raise
    finally:
        if os.getpid()==owner_pid:
            signal.alarm(0)
            if active_child is not None:
                try:os.kill(active_child,signal.SIGKILL)
                except ProcessLookupError:pass
                try:os.waitpid(active_child,0)
                except ChildProcessError:pass


if __name__=="__main__":main()
