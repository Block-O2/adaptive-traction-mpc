function paths = r4_source_paths(repo_root)
%R4_SOURCE_PATHS Frozen R3C formal evidence consumed read-only by R4.

if nargin < 1 || strlength(string(repo_root)) == 0
    here = fileparts(mfilename('fullpath'));
    repo_root = fileparts(fileparts(fileparts(fileparts(here))));
end
local_root = fullfile(repo_root,'linkage','results','local', ...
    'r3c_constraint_aware_reference_layer');
paths = struct();
paths.stage1_oracle = fullfile(local_root,'20260816_151618', ...
    'stage1_oracle','formal_oracle_gate.mat');
paths.stage2_adaptive = fullfile(local_root,'20260816_152124', ...
    'stage2_adaptive','formal_adaptive_results.mat');
paths.output_root = fullfile(repo_root,'linkage','results','local', ...
    'r4_minimal_recovery_corridor');
end
