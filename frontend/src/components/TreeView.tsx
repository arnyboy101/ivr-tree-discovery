import { useMemo, useEffect, useRef } from 'react';
import {
  ReactFlow,
  Background,
  Controls as FlowControls,
  Position,
  useReactFlow,
  ReactFlowProvider,
  type Node as RFNode,
  type Edge as RFEdge,
} from '@xyflow/react';
import Dagre from '@dagrejs/dagre';
import '@xyflow/react/dist/style.css';
import type { IVRNode, IVREdge } from '../types';
import { IVRNodeComponent, type IVRNodeData } from './IVRNode';

interface TreeViewProps {
  nodes: IVRNode[];
  edges: IVREdge[];
  onNodeClick?: (nodeId: string) => void;
}

const NODE_WIDTH = 240;
const NODE_HEIGHT = 80;

const nodeTypes = { ivr: IVRNodeComponent };

function getLayoutedElements(nodes: RFNode[], edges: RFEdge[]) {
  const g = new Dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: 'TB', nodesep: 80, ranksep: 120 });

  nodes.forEach((node) => g.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT }));
  edges.forEach((edge) => g.setEdge(edge.source, edge.target));

  Dagre.layout(g);

  const layoutedNodes = nodes.map((node) => {
    const pos = g.node(node.id);
    return {
      ...node,
      position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 },
    };
  });

  return { nodes: layoutedNodes, edges };
}

function nodeLabel(node: IVRNode): string {
  if (node.status === 'calling') return 'Calling...';
  if (node.status === 'parsing') return 'Parsing transcript...';
  if (node.prompt_text) {
    const text = node.prompt_text.substring(0, 100);
    return text + (node.prompt_text.length > 100 ? '...' : '');
  }
  if (!node.parent_id) return 'Root';
  return node.dtmf_path || 'Pending';
}

function TreeViewInner({ nodes, edges, onNodeClick }: TreeViewProps) {
  const { fitView } = useReactFlow();
  const fitViewTimer = useRef<ReturnType<typeof setTimeout>>();

  // Build a map of node_id -> edge label for display on child nodes
  const edgeLabelMap = useMemo(() => {
    const map: Record<string, string> = {};
    for (const edge of edges) {
      if (edge.to_node_id) {
        map[edge.to_node_id] = edge.label || `Key ${edge.dtmf_key}`;
      }
    }
    return map;
  }, [edges]);

  const rfNodes: RFNode[] = useMemo(() => {
    return nodes.map((node) => {
      const data: IVRNodeData = {
        label: nodeLabel(node),
        edgeLabel: edgeLabelMap[node.id] || '',
        status: node.status,
        cost: node.cost,
        isRoot: !node.parent_id,
      };
      return {
        id: node.id,
        type: 'ivr',
        position: { x: 0, y: 0 },
        data,
        sourcePosition: Position.Bottom,
        targetPosition: Position.Top,
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
        style: { width: NODE_WIDTH },
      };
    });
  }, [nodes, edgeLabelMap]);

  const rfEdges: RFEdge[] = useMemo(() => {
    return edges
      .filter((e) => e.to_node_id)
      .map((edge) => {
        const targetNode = nodes.find((n) => n.id === edge.to_node_id);
        const isActive =
          targetNode?.status === 'calling' || targetNode?.status === 'parsing';

        return {
          id: edge.id,
          source: edge.from_node_id,
          target: edge.to_node_id!,
          type: 'default',
          label: `${edge.dtmf_key}`,
          style: {
            stroke: isActive ? '#F59E0B' : '#6B7280',
            strokeWidth: 2,
          },
          labelStyle: {
            fill: isActive ? '#FCD34D' : '#9CA3AF',
            fontSize: '11px',
            fontWeight: 600,
          },
          labelBgStyle: {
            fill: '#030712',
            fillOpacity: 0.95,
          },
          labelBgPadding: [6, 3] as [number, number],
          labelBgBorderRadius: 6,
          animated: isActive,
        };
      });
  }, [edges, nodes]);

  const layouted = useMemo(
    () => getLayoutedElements(rfNodes, rfEdges),
    [rfNodes, rfEdges]
  );

  // Debounced fitView — triggers whenever tree structure changes.
  // Uses debounce so rapid updates (multiple nodes/edges arriving)
  // only cause one fitView after they settle.
  const structureKey = `${nodes.length}-${edges.length}`;
  useEffect(() => {
    clearTimeout(fitViewTimer.current);
    fitViewTimer.current = setTimeout(() => {
      fitView({ padding: 0.3, duration: 300 });
    }, 200);
    return () => clearTimeout(fitViewTimer.current);
  }, [structureKey, fitView]);

  return (
    <ReactFlow
      nodes={layouted.nodes}
      edges={layouted.edges}
      nodeTypes={nodeTypes}
      onNodeClick={(_event, node) => onNodeClick?.(node.id)}
      fitView
      fitViewOptions={{ padding: 0.3 }}
      proOptions={{ hideAttribution: true }}
      minZoom={0.1}
      maxZoom={2.5}
    >
      <Background color="#1a1a2e" gap={32} size={1} />
      <FlowControls
        showInteractive={false}
        style={{
          background: '#111827',
          borderColor: '#1F2937',
          borderRadius: '10px',
          boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
        }}
      />
    </ReactFlow>
  );
}

export function TreeView(props: TreeViewProps) {
  return (
    <ReactFlowProvider>
      <TreeViewInner {...props} />
    </ReactFlowProvider>
  );
}
