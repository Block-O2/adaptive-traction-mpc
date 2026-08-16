function [rank_value,tolerance,condition_number,singular_values,V] = ...
        r3a_effective_rank(matrix)
%R3A_EFFECTIVE_RANK Apply the exact R2B numerical-rank convention.

[~,S,V]=svd(matrix,'econ');singular_values=diag(S);
if isempty(singular_values) || singular_values(1)<=0
    tolerance=0;rank_value=0;condition_number=Inf;return;
end
tolerance=max(size(matrix))*eps(singular_values(1));
rank_value=sum(singular_values>tolerance);
if rank_value<size(matrix,2) || singular_values(end)<=0
    condition_number=Inf;
else
    condition_number=singular_values(1)/singular_values(end);
end
for column=1:size(V,2)
    [~,index]=max(abs(V(:,column)));
    if V(index,column)<0,V(:,column)=-V(:,column);end
end
end
