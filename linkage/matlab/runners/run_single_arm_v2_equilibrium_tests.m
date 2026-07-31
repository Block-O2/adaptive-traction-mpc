function run_single_arm_v2_equilibrium_tests()
%RUN_SINGLE_ARM_V2_EQUILIBRIUM_TESTS Headless full MATLAB regression.

set(groot, 'DefaultFigureVisible', 'off');
runner_dir = fileparts(mfilename('fullpath'));
repo_root = fileparts(fileparts(fileparts(runner_dir)));
test_dir = fullfile(repo_root, 'linkage', 'matlab', 'tests');
output_dir = fullfile(repo_root, 'linkage', 'results', 'local', ...
    'single_arm_v2_equilibrium_baseline');
if ~isfolder(output_dir)
    mkdir(output_dir);
end
diary_path = fullfile(output_dir, 'test_console.log');
if isfile(diary_path)
    delete(diary_path);
end
diary(diary_path);
cleanup = onCleanup(@() diary('off'));

fprintf('SINGLE ARM V2 EQUILIBRIUM TESTS MATLAB: %s\n', version);
fprintf('FULL MATLAB REGRESSION DIRECTORY: %s\n', test_dir);
results = runtests(test_dir, 'IncludeSubfolders', true);
disp(results);
summary = struct();
summary.matlab_version = version;
summary.total = numel(results);
summary.passed = sum([results.Passed]);
summary.failed = sum([results.Failed]);
summary.incomplete = sum([results.Incomplete]);
summary.generated_utc = char(datetime('now', 'TimeZone', 'UTC', ...
    'Format', 'yyyy-MM-dd HH:mm:ss.SSS XXX'));
save(fullfile(output_dir, 'test_summary.mat'), 'summary');
fprintf(['SINGLE ARM V2 TEST SUMMARY: total=%d passed=%d ' ...
    'failed=%d incomplete=%d\n'], summary.total, summary.passed, ...
    summary.failed, summary.incomplete);
if summary.failed > 0 || summary.incomplete > 0
    error('SingleArmV2:TestsFailed', ...
        'One or more MATLAB regression tests failed or were incomplete.');
end
end
