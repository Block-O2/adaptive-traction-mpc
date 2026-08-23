function manifest = r4_source_manifest(paths)
%R4_SOURCE_MANIFEST Byte, timestamp, and SHA-256 mutation guard.

names = ["stage1_oracle";"stage2_adaptive"];
values = [string(paths.stage1_oracle);string(paths.stage2_adaptive)];
bytes = zeros(2,1); modified = zeros(2,1); sha256 = strings(2,1);
for index = 1:2
    info = dir(values(index));
    if isempty(info)
        error('R4:MissingFormalSource', ...
            'Required frozen R3C source is missing: %s',values(index));
    end
    bytes(index) = info.bytes;
    modified(index) = info.datenum;
    sha256(index) = file_sha256(values(index));
end
manifest = table(names,values,bytes,modified,sha256, ...
    'VariableNames',{'source','path','bytes','modified_datenum','sha256'});
end

function digest = file_sha256(path)
engine = java.security.MessageDigest.getInstance('SHA-256');
file = java.io.FileInputStream(char(path));
cleanup = onCleanup(@() file.close()); %#ok<NASGU>
buffer = zeros(1,1024*1024,'int8');
while true
    count = file.read(buffer,0,numel(buffer));
    if count < 0, break; end
    engine.update(buffer(1:count));
end
raw = typecast(engine.digest(),'uint8');
digest = lower(string(reshape(dec2hex(raw,2)',1,[])));
end
