function graph = r4_graph_search(domain,anchor,model_kind,support_mode,rate_deg_s)
%R4_GRAPH_SEARCH BFS on local dynamically feasible lattice edges.

n=numel(domain.s);goal_indices=find(domain.is_goal);
graph=struct('classification',"NO_RECOVERY_POINT_FOUND", ...
    'point_found',~isempty(goal_indices),'connected',false, ...
    'seed_count',0,'visited_count',0,'path_indices',zeros(0,1), ...
    'path_q_rad',zeros(2,0),'path_s',zeros(0,1), ...
    'minimum_force_margin_N',NaN,'maximum_residual_Nm',NaN);
if isempty(goal_indices),return;end
transit=find(domain.is_transit);seed=zeros(0,1);
for idx=reshape(transit,1,[])
    if max(abs(rad2deg(domain.q_rad(:,idx)-anchor.q_rad)))<=1.5+1e-12
        edge=r4_initial_connection(domain.q_rad(:,idx),anchor, ...
            model_kind,support_mode);
        if edge.feasible,seed(end+1,1)=idx;end %#ok<AGROW>
    end
end
graph.seed_count=numel(seed);
if isempty(seed)
    graph.classification="FEASIBLE_POINT_DISCONNECTED";return;
end
visited=false(n,1);parent=zeros(n,1);queue=zeros(n,1);
head=1;tail=numel(seed);queue(1:tail)=seed;visited(seed)=true;
goal=0;
while head<=tail
    current=queue(head);head=head+1;
    if domain.is_goal(current),goal=current;break;end
    candidates=find(domain.is_transit & ~visited & ...
        abs(domain.s-domain.s(current))<=0.0100001 & ...
        max(abs(rad2deg(domain.q_rad-domain.q_rad(:,current))),[],1)' ...
        <=1.5+1e-12);
    for next=reshape(candidates,1,[])
        if next==current,continue;end
        edge=r4_local_edge_feasibility(domain.q_rad(:,current), ...
            domain.q_rad(:,next),anchor,model_kind,support_mode,rate_deg_s);
        if edge.feasible
            visited(next)=true;parent(next)=current;tail=tail+1;queue(tail)=next;
        end
    end
end
graph.visited_count=sum(visited);
if goal==0
    graph.classification="FEASIBLE_POINT_DISCONNECTED";return;
end
path=goal;
while parent(path(1))~=0,path=[parent(path(1));path];end %#ok<AGROW>
graph.classification="CONTINUOUS_RECOVERY_CORRIDOR_EXISTS";
graph.connected=true;graph.path_indices=path;
graph.path_q_rad=domain.q_rad(:,path);graph.path_s=domain.s(path);
graph.minimum_force_margin_N=min(domain.force_margin_N(path));
graph.maximum_residual_Nm=max(domain.residual_Nm(path));
end
