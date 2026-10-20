# Feasibility audit

All seven necessary static prechecks pass. No primary time integration occurred.

Static inputs: exact seven compiled MuJoCo models; unchanged Human hard ROM [0,125]deg, 5deg soft margin; original robot limits; force 200N/moment60Nm; original task velocity/acceleration/HOLD/RETURN/scorer limits. Structural shank bound .46m contains .40076m. No range or margin expanded.

Three distinct cuff geometric paths: 129/129 IK samples, no initial penetration, original analytic limb/sleeve/bar/adapter margins ≥ original clearance floor. Mass/stiffness cases have identical geometric bodies/poses and reuse nominal IK samples, each with their own separately verified physical model. No between-sample robot swept-contact proof, nonlinear dynamic feasibility or clinical safety proof.

HOLD endpoint and reverse RETURN geometry screened only. No force/moment/velocity/acceleration trajectory verdict exists before execution. Setup-domain failures must be PHYSICAL_SETUP_OUT_OF_SCOPE, not identification failures. See exact numerical evidence and limits in FEASIBILITY_AUDIT.json.
