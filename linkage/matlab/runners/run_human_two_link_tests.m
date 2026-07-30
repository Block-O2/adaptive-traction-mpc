function run_human_two_link_tests()
%RUN_HUMAN_TWO_LINK_TESTS Headless official test entry point.

set(groot, 'DefaultFigureVisible', 'off');
runner_dir = fileparts(mfilename('fullpath'));
repo_root = fileparts(fileparts(fileparts(runner_dir)));
test_dir = fullfile(repo_root, 'linkage', 'matlab', 'tests');
output_dir = fullfile(repo_root, 'linkage', 'results', 'local', ...
    'human_two_link_baseline');
if ~isfolder(output_dir)
    mkdir(output_dir);
end

fprintf('HUMAN TWO-LINK TESTS MATLAB: %s\n', version);
fprintf('HUMAN TWO-LINK TEST DIRECTORY: %s\n', test_dir);
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

fprintf('HUMAN TWO-LINK TEST SUMMARY: total=%d passed=%d failed=%d incomplete=%d\n', ...
    summary.total, summary.passed, summary.failed, summary.incomplete);
if summary.failed > 0 || summary.incomplete > 0
    error('HumanTwoLink:TestsFailed', ...
        'One or more official MATLAB tests failed or were incomplete.');
end
end
