function manifest = r3a_source_manifest(paths)
%R3A_SOURCE_MANIFEST Read-only file metadata used as a mutation guard.

names=["r1";"r2a";"r2b"];
path_values=[string(paths.r1);string(paths.r2a);string(paths.r2b)];
bytes=zeros(3,1);modified=zeros(3,1);modified_text=strings(3,1);
for index=1:3
    info=dir(path_values(index));
    if isempty(info)
        error('R3A:MissingFormalSource', ...
            'Required formal source is missing: %s',path_values(index));
    end
    bytes(index)=info.bytes;modified(index)=info.datenum;
    modified_text(index)=string(info.date);
end
manifest=table(names,path_values,bytes,modified,modified_text, ...
    'VariableNames',{'source','path','bytes','modified_datenum', ...
    'modified_text'});
end
