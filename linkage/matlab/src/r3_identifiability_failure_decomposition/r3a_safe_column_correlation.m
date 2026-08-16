function correlation = r3a_safe_column_correlation(matrix)
%R3A_SAFE_COLUMN_CORRELATION Cosine correlation with zero-column handling.

count=size(matrix,2);correlation=zeros(count,count);
norms=vecnorm(matrix,2,1);
for row=1:count
    for column=1:count
        if norms(row)<=eps || norms(column)<=eps
            correlation(row,column)=double(row==column && norms(row)>eps);
        else
            correlation(row,column)= ...
                matrix(:,row)'*matrix(:,column)/(norms(row)*norms(column));
        end
    end
end
correlation=min(max(correlation,-1),1);
end
