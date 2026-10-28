import { expect, test } from 'vitest';
import { buildElements } from './use-elements';

const route = (as_path: number[]) =>
  ({ as_path }) as unknown as StructuredResponse['routes'][number];

test('buildElements - shares one node per ASN across paths', () => {
  const data = {
    routes: [route([65000, 174, 13335]), route([65000, 3356, 13335]), route([65000, 174, 13335])],
    asn_organizations: {},
  } as unknown as BGPStructuredOutput;
  const elements = [...buildElements({ asn: '65000', name: 'Lab' }, data)];
  const nodes = elements.filter(element => 'position' in element).map(element => element.id);
  const edges = elements.filter(element => 'source' in element).map(element => element.id);

  expect(nodes.sort()).toEqual(['13335', '174', '3356', '65000']);
  expect(edges.sort()).toEqual(['e174-13335', 'e3356-13335', 'e65000-174', 'e65000-3356']);
});
