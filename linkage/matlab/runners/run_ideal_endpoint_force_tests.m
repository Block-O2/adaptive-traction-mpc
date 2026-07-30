function run_ideal_endpoint_force_tests()
%RUN_IDEAL_ENDPOINT_FORCE_TESTS Headless endpoint-force regression entry point.

set(groot, 'DefaultFigureVisible', 'off');
runner_dir = fileparts(mfilename('fullpath'));
repo_root = fileparts(fileparts(fileparts(runner_dir)));
test_dir = fullfile(repo_root, 'linkage', 'matlab', 'tests');
output_dir = fullfile(repo_root, 'linkage', 'results', 'local', ...
    'ideal_endpoint_force_baseline');
if ~isfolder(output_dir)
    mkdir(output_dir);
end

diary_path = fullfile(output_dir, 'test_console.log');
if isfile(diary_path)
    delete(diary_path);
end
diary(diary_path);
diary_cleanup = onCleanup(@() diary('off'));

fprintf('IDEAL ENDPOINT FORCE TESTS MATLAB: %s\n', version);
fprintf('IDEAL ENDPOINT FORCE TEST DIRECTORY: %s\n', test_dir);
results = runtests(test_dir, 'IncludeSubfolders', false);
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

fprintf(['IDEAL ENDPOINT FORCE TEST SUMMARY: total=%d passed=%d ' ...
    'failed=%d incomplete=%d\n'], ...
    summary.total, summary.passed, summary.failed, summary.incomplete);
if summary.failed > 0 || summary.incomplete > 0
    error('IdealEndpointForce:TestsFailed', ...
        'One or more MATLAB tests failed or were incomplete.');
end
end
