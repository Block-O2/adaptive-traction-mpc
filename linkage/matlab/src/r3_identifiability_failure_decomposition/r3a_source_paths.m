function paths = r3a_source_paths(repo_root)
%R3A_SOURCE_PATHS Frozen formal sources for the offline R3A audit.

if nargin<1 || strlength(string(repo_root))==0
    here=fileparts(mfilename('fullpath'));
    repo_root=fileparts(fileparts(fileparts(fileparts(here))));
end
local_root=fullfile(repo_root,'linkage','results','local');
paths=struct();
paths.r1=fullfile(local_root,'dynamic_robust_load_transfer_v1', ...
    '20260815_171801','formal_results.mat');
paths.r2a=fullfile(local_root, ...
    'dynamic_robust_load_transfer_v1_oracle_model_r2a', ...
    '20260815_174540','formal_oracle_results.mat');
paths.r2b=fullfile(local_root, ...
    'dynamic_robust_load_transfer_v1_adaptive_tracking_r2b', ...
    '20260816_083505','formal_adaptive_results.mat');
paths.output_root=fullfile(local_root, ...
    'r3_identifiability_failure_decomposition');
end
