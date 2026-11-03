"use client";
// Схема флоу на React Flow (@xyflow/react — как схема политики DocOps): этапы — узлы, переходы — стрелки.
// Состояние — документ флоу; узлы и стрелки выводятся из него (lib/flow.ts), правки возвращаются через onChange.
import { Background, Controls, Handle, MarkerType, Position, ReactFlow, useNodesState, type Edge, type Node,
  type NodeProps } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useEffect, useMemo, useState } from "react";
import { addStage, connect, type EdgeKind, type Flow, graph, moveNode, removeStage, removeTransition,
  updateStage } from "@/lib/flow";
import { Button, Field, Input, Select } from "./ui";

type Tutor = { key: string; name: string };
type StageData = { label: string; lead: string; fixed: boolean; first: boolean; last: boolean };

function StageNode({ data, selected }: NodeProps<Node<StageData>>) {
  const tone = data.fixed ? "border-zinc-400 bg-zinc-100 dark:bg-zinc-800"
    : "border-indigo-300 bg-white dark:border-indigo-700 dark:bg-zinc-900";
  return (
    <div className={`min-w-40 rounded-lg border-2 px-3 py-2 text-xs shadow-sm ${tone} ${selected ? "ring-2 ring-indigo-500" : ""}`}>
      {!data.first && <>
        <Handle type="target" position={Position.Left} id="l-in" />
        <Handle type="target" position={Position.Bottom} id="b-in" style={{ left: "35%" }} />
      </>}
      <div className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{data.label}</div>
      <div className="mt-0.5 text-zinc-500">{data.lead}</div>
      {!data.last && <>
        <Handle type="source" position={Position.Right} id="r-out" />
        <Handle type="source" position={Position.Bottom} id="b-out" style={{ left: "65%" }} />
      </>}
    </div>
  );
}

const nodeTypes = { stage: StageNode };
const EDGE_STYLE: Record<EdgeKind, { stroke: string; strokeDasharray?: string }> = {
  handoff: { stroke: "#6366f1" }, return: { stroke: "#d97706", strokeDasharray: "6 4" }, close: { stroke: "#059669" },
};

type Selection = { kind: "stage"; id: string } | { kind: "edge"; from: string; to: string } | null;

export function FlowGraph({ flow, tutors, onChange }: { flow: Flow; tutors: Tutor[]; onChange: (f: Flow) => void }) {
  const g = useMemo(() => graph(flow), [flow]);
  const names = Object.fromEntries(tutors.map((t) => [t.key, t.name]));
  const toNodes = (): Node<StageData>[] => g.nodes.map((n) => ({ id: n.id, type: "stage", position: n.position,
    deletable: false, data: { label: n.label, fixed: n.fixed, first: n.id === "todo", last: n.id === "done",
      lead: n.id === "todo" ? "задания ждут начала" : n.id === "done" ? "все проверки прошли"
        : `ведёт: ${n.agent ? names[n.agent] ?? `${n.agent} (выключен)` : "агент задания"}` } }));
  // узлы — сразу на первом рендере: fitView подбирает масштаб по ним, а не по пустой схеме
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<StageData>>(toNodes());
  const [selected, setSelected] = useState<Selection>(null);
  useEffect(() => { setNodes(toNodes()); }, [g, tutors]); // eslint-disable-line react-hooks/exhaustive-deps

  const isSel = (e: { source: string; target: string }) =>
    selected?.kind === "edge" && selected.from === e.source && selected.to === e.target;
  const edges: Edge[] = g.edges.map((e) => ({
    id: e.id, source: e.source, target: e.target, type: "smoothstep", deletable: false, selected: isSel(e),
    sourceHandle: e.kind === "return" ? "b-out" : "r-out", targetHandle: e.kind === "return" ? "b-in" : "l-in",
    style: { ...EDGE_STYLE[e.kind], strokeWidth: isSel(e) ? 3 : 1.5 },
    markerEnd: { type: MarkerType.ArrowClosed, color: EDGE_STYLE[e.kind].stroke },
  }));
  const stage = selected?.kind === "stage" ? flow.stages.find((s) => s.key === selected.id) : undefined;
  const label = (key: string) => flow.stages.find((s) => s.key === key)?.name ?? key;

  return (
    <div className="flex flex-col gap-4 lg:flex-row">
      <div className="h-[460px] flex-1 rounded-lg border border-zinc-200 dark:border-zinc-800">
        <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} onNodesChange={onNodesChange} fitView
          fitViewOptions={{ padding: 0.2 }} minZoom={0.3} snapToGrid snapGrid={[10, 10]}
          onNodeDragStop={(_e, n) => onChange(moveNode(flow, n.id, n.position))}
          onConnect={(c) => { if (c.source && c.target) onChange(connect(flow, c.source, c.target)); }}
          onNodeClick={(_e, n) => setSelected({ kind: "stage", id: n.id })}
          onEdgeClick={(_e, e) => setSelected({ kind: "edge", from: e.source, to: e.target })}
          onPaneClick={() => setSelected(null)}>
          <Background gap={20} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
      <aside className="space-y-4 text-sm lg:w-72 lg:shrink-0">
        <div className="rounded-lg border border-zinc-200 p-3 text-xs text-zinc-500 dark:border-zinc-800">
          <div className="mb-1"><span className="text-indigo-500">━</span> дальше · <span className="text-amber-600">┅</span> назад ·
            {" "}<span className="text-emerald-600">━</span> в «Готово» (только по проверкам)</div>
          Перетаскивайте этапы; потяните от точки справа или снизу к другому этапу — новый переход. Клик по этапу или
          стрелке — её настройки.
        </div>
        {stage && <div className="space-y-2 rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
          <div className="font-semibold">Этап</div>
          <Field label="Название"><Input value={stage.name} maxLength={40}
            onChange={(e) => onChange(updateStage(flow, stage.key, { name: e.target.value }))} /></Field>
          {stage.key !== "todo" && stage.key !== "done" && <>
            <Field label="Кто ведёт задание на этом этапе">
              <Select value={stage.agent_key ?? ""}
                onChange={(e) => onChange(updateStage(flow, stage.key, { agent_key: e.target.value || null }))}>
                <option value="">агент задания (выбрал методист)</option>
                {tutors.map((a) => <option key={a.key} value={a.key}>{a.name}</option>)}
              </Select></Field>
            <Button variant="danger" onClick={() => { onChange(removeStage(flow, stage.key)); setSelected(null); }}>
              Убрать этап</Button>
          </>}
        </div>}
        {selected?.kind === "edge" && <div className="space-y-2 rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
          <div className="font-semibold">{label(selected.from)} → {label(selected.to)}</div>
          {selected.to === "done" && <p className="text-xs text-zinc-500">Карточка попадёт в «Готово», только если
            прошли все проверочные команды задания.</p>}
          <Button variant="danger" onClick={() => { onChange(removeTransition(flow, selected.from, selected.to));
            setSelected(null); }}>Удалить переход</Button>
        </div>}
        <Button variant="secondary" onClick={() => onChange(addStage(flow))}>+ Этап</Button>
      </aside>
    </div>
  );
}
