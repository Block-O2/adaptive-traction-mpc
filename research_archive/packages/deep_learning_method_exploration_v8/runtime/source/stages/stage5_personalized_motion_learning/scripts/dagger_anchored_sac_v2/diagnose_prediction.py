from common import *
def run():
 a=actor();a.load_state_dict(torch.load(V/'qualified_actor.pt',map_location='cpu',weights_only=False)['state_dict']);a.eval();z=np.load(V/'round_04/evaluation_1/episode_00001/POLICY_TRANSITIONS.npz');new=np.load(O/'baseline/frozen_student_NATIVE/episode_00001/TRANSITIONS.npz');obs=torch.as_tensor(z['observations'])
 with torch.no_grad():direct=a(obs,True).numpy()
 predict,_=a.predict(z['observations'],deterministic=True);first=a(torch.as_tensor(z['observations'][:1]),True).detach().numpy()[0];firstpred,_=a.predict(z['observations'][0],deterministic=True)
 save('PREDICTION_PATH_DIAGNOSIS.json',dict(direct_vs_predict_max_difference=float(np.max(np.abs(direct-predict))),direct_vs_predict_different_values=int(np.count_nonzero(direct!=predict)),first_direct=first,first_predict=firstpred,archived_first_action=z['actions'][0],failed_new_first_action=new['actions'][0],initial_observation_equal=np.array_equal(z['observations'][0],new['observations'][0]),first_new_vs_archive_diff=float(np.max(np.abs(new['actions'][0]-z['actions'][0]))),explanation='BasePolicy.predict unscale_action for [-1,1] still applies low + .5*(scaled+1)*(high-low); mathematically identity but float32 cancellation changes proposal at a few ulps. Reuse exact legacy prediction path; no physical/interface change.'))
 print(json.dumps(read('PREDICTION_PATH_DIAGNOSIS.json')),flush=True)
if __name__=='__main__':run()
