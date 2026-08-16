function run_linkage_tests()
%RUN_LINKAGE_TESTS Headless regression entry point for retained active code.

set(groot, 'DefaultFigureVisible', 'off');
runner_dir = fileparts(mfilename('fullpath'));
repo_root = fileparts(fileparts(fileparts(runner_dir)));
test_root = fullfile(repo_root, 'linkage', 'matlab', 'tests');
v2_test_dir = fullfile(test_root, 'v2');
equilibrium_test_dir = fullfile(test_root, 'v2_equilibrium');
atlas_test_dir = fullfile(test_root, 'quasistatic_atlas');
force_mode_test_dir = fullfile(test_root, 'near_extension_force_mode');
hybrid_tube_test_dir = fullfile(test_root, 'hybrid_tube_v1');
bed_supported_test_dir = fullfile(test_root, 'bed_supported_v1');
dynamic_robust_test_dir = fullfile(test_root, ...
    'dynamic_robust_load_transfer_v1');
r3a_test_dir = fullfile(test_root, ...
    'r3_identifiability_failure_decomposition');
output_dir = fullfile(repo_root, 'linkage', 'results', 'local', ...
    'linkage_tests');
if ~isfolder(output_dir)
    mkdir(output_dir);
end

diary_path = fullfile(output_dir, 'test_console.log');
if isfile(diary_path)
    delete(diary_path);
end
diary(diary_path);
cleanup = onCleanup(@() diary('off'));

fprintf('LINKAGE ACTIVE TESTS MATLAB: %s\n', version);
fprintf('V2 TEST DIRECTORY: %s\n', v2_test_dir);
fprintf('EQUILIBRIUM TEST DIRECTORY: %s\n', equilibrium_test_dir);
fprintf('QUASISTATIC ATLAS TEST DIRECTORY: %s\n', atlas_test_dir);
fprintf('NEAR-EXTENSION FORCE-MODE TEST DIRECTORY: %s\n', ...
    force_mode_test_dir);
fprintf('HYBRID TUBE V1 TEST DIRECTORY: %s\n', hybrid_tube_test_dir);
fprintf('BED-SUPPORTED V1 TEST DIRECTORY: %s\n', bed_supported_test_dir);
fprintf('DYNAMIC ROBUST V1 TEST DIRECTORY: %s\n', dynamic_robust_test_dir);
fprintf('R3A OFFLINE ANALYSIS TEST DIRECTORY: %s\n', r3a_test_dir);
v2_results = runtests(v2_test_dir, 'IncludeSubfolders', false);
equilibrium_results = runtests(equilibrium_test_dir, ...
    'IncludeSubfolders', false);
atlas_results = runtests(atlas_test_dir, 'IncludeSubfolders', false);
force_mode_results = runtests(force_mode_test_dir, ...
    'IncludeSubfolders', false);
hybrid_tube_results = runtests(hybrid_tube_test_dir, ...
    'IncludeSubfolders', false);
bed_supported_results = runtests(bed_supported_test_dir, ...
    'IncludeSubfolders', false);
dynamic_robust_results = runtests(dynamic_robust_test_dir, ...
    'IncludeSubfolders', false);
r3a_results = runtests(r3a_test_dir, 'IncludeSubfolders', false);
results = [v2_results(:); equilibrium_results(:); atlas_results(:); ...
    force_mode_results(:); hybrid_tube_results(:); ...
    bed_supported_results(:); dynamic_robust_results(:); r3a_results(:)];
disp(results);

summary = struct();
summary.matlab_version = version;
summary.total = numel(results);
summary.passed = sum([results.Passed]);
summary.failed = sum([results.Failed]);
summary.incomplete = sum([results.Incomplete]);
summary.generated_utc = char(datetime('now', 'TimeZone', 'UTC', ...
    'Format', 'yyyy-MM-dd HH:mm:ss.SSS XXX'));
summary.test_directories = {v2_test_dir; equilibrium_test_dir; ...
    atlas_test_dir; force_mode_test_dir; hybrid_tube_test_dir};
summary.test_directories{end+1} = bed_supported_test_dir;
summary.test_directories{end+1} = dynamic_robust_test_dir;
summary.test_directories{end+1} = r3a_test_dir;
save(fullfile(output_dir, 'test_summary.mat'), 'summary');

fprintf(['LINKAGE ACTIVE TEST SUMMARY: total=%d passed=%d failed=%d ' ...
    'incomplete=%d\n'], summary.total, summary.passed, summary.failed, ...
    summary.incomplete);
if summary.failed > 0 || summary.incomplete > 0
    error('Linkage:TestsFailed', ...
        'One or more retained MATLAB tests failed or were incomplete.');
end
end
