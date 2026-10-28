import dagre from 'dagre';
import { useMemo } from 'react';

import type { Edge, Node } from 'reactflow';
import type { NodeData } from './chart';

interface BasePath {
  asn: string;
  name: string;
}

type FlowElement<T> = Node<T> | Edge<T>;

const NODE_WIDTH = 128;
const NODE_HEIGHT = 48;

export function useElements(base: BasePath, data: AllStructuredResponses): FlowElement<NodeData>[] {
  return useMemo(() => {
    return [...buildElements(base, data)];
  }, [base, data]);
}

/**
 * Check if data contains BGP routes
 */
function isBGPData(data: AllStructuredResponses): data is BGPStructuredOutput {
  return 'routes' in data && Array.isArray(data.routes);
}

/**
 * Check if data contains traceroute hops
 */
function isTracerouteData(data: AllStructuredResponses): data is TracerouteStructuredOutput {
  return 'hops' in data && Array.isArray(data.hops);
}

/**
 * Calculate the positions for each AS Path.
 * @see https://github.com/MrBlenny/react-flow-chart/issues/61
 */
export function* buildElements(
  base: BasePath,
  data: AllStructuredResponses,
): Generator<FlowElement<NodeData>> {
  let asPaths: string[][] = [];
  let asnOrgs: Record<string, { name?: string; country?: string }> = {};
  // For traceroute data we may have IXPs represented as asn === 'IXP' with
  // the IXP name stored per-hop in hop.org. Collect per-path org arrays so
  // nodes for IXPs can show the proper IXP name instead of the generic
  // "IXP" label.
  const pathGroupOrgs: Record<number, Array<string | undefined>> = {};

  if (isBGPData(data)) {
    // Handle BGP routes with AS paths
    const { routes } = data;
    asPaths = routes
      .filter(r => r.as_path.length !== 0)
      .map(r => {
        const uniqueAsns = [...new Set(r.as_path.map(asn => String(asn)))];
        // Remove the base ASN if it's the first hop to avoid duplication
        return uniqueAsns[0] === base.asn ? uniqueAsns.slice(1) : uniqueAsns;
      })
      .filter(path => path.length > 0); // Remove empty paths

    // Get ASN organization mapping if available
    asnOrgs = data.asn_organizations || {};

    // Debug: Log BGP ASN organization data
    if (Object.keys(asnOrgs).length > 0) {
      console.debug('BGP ASN organizations loaded:', asnOrgs);
    } else {
      console.warn('BGP ASN organizations not found or empty');
    }
  } else if (isTracerouteData(data)) {
    // Handle traceroute hops - build AS path from hop ASNs
    const hopAsns: string[] = [];
    const hopOrgs: Array<string | undefined> = [];
    let currentAsn = '';

    for (const hop of data.hops) {
      if (hop.asn && hop.asn !== 'None' && hop.asn !== currentAsn) {
        currentAsn = hop.asn;
        hopAsns.push(hop.asn);
        hopOrgs.push(hop.org ?? undefined);
      }
    }

    if (hopAsns.length > 0) {
      // Remove the base ASN if it's the first hop to avoid duplication
      const removeBase = hopAsns[0] === base.asn;
      const filteredAsns = removeBase ? hopAsns.slice(1) : hopAsns;
      const filteredOrgs = removeBase ? hopOrgs.slice(1) : hopOrgs;
      if (filteredAsns.length > 0) {
        asPaths = [filteredAsns];
        pathGroupOrgs[0] = filteredOrgs;
      }
    }

    // Get ASN organization mapping if available
    asnOrgs = data.asn_organizations || {};

    // Debug: Log traceroute ASN organization data
    if (Object.keys(asnOrgs).length > 0) {
      console.debug('Traceroute ASN organizations loaded:', asnOrgs);
    } else {
      console.warn('Traceroute ASN organizations not found or empty');
    }
  }

  if (asPaths.length === 0) {
    return;
  }

  const g = new dagre.graphlib.Graph();
  g.setGraph({
    marginx: 20,
    marginy: 20,
    rankdir: 'BT',
    ranksep: NODE_HEIGHT * 2,
  });
  g.setDefaultEdgeLabel(() => ({}));

  // Set the origin (i.e., the hyperglass user) at the base.
  g.setNode(base.asn, { width: NODE_WIDTH, height: NODE_HEIGHT });

  // One node per ASN, shared by every path that crosses it. IXPs carry no ASN, so
  // each distinct IXP name gets its own node.
  const nodes = new Map<string, { asn: string; name: string }>();
  const edges = new Map<string, Edge<NodeData>>();

  for (const [groupIdx, pathGroup] of asPaths.entries()) {
    let previous = base.asn;
    for (const [idx, asn] of pathGroup.entries()) {
      let node = asn;
      let name = asnOrgs[asn]?.name || (asn === '0' ? 'Private/Unknown' : `AS${asn}`);
      if (asn === 'IXP') {
        const ixpName = pathGroupOrgs[groupIdx]?.[idx];
        name = ixpName && ixpName !== 'None' ? ixpName : 'IXP';
        node = `IXP-${name}`;
      }
      if (!nodes.has(node)) {
        nodes.set(node, { asn, name });
        g.setNode(node, { width: NODE_WIDTH, height: NODE_HEIGHT });
      }
      const id = `e${previous}-${node}`;
      if (previous !== node && !edges.has(id)) {
        g.setEdge(previous, node);
        edges.set(id, { id, source: previous, target: node });
      }
      previous = node;
    }
  }

  // Now that that nodes are added, create the layout.
  dagre.layout(g);

  const hasChildren = new Set([...edges.values()].map(edge => edge.source));

  for (const edge of edges.values()) {
    yield edge;
  }

  for (const [id, { asn, name }] of [
    [base.asn, { asn: base.asn, name: asnOrgs[base.asn]?.name || base.name }] as const,
    ...nodes,
  ]) {
    const position = g.node(id);
    yield {
      id,
      type: 'ASNode',
      position: { x: position.x - NODE_WIDTH / 2, y: position.y - NODE_HEIGHT / 2 },
      data: {
        asn: `${asn}`,
        name,
        hasChildren: hasChildren.has(id),
        hasParents: id !== base.asn,
      },
    };
  }
}
