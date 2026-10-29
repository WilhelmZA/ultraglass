import { beforeAll, describe, expect, it, vi } from 'vitest';
import { render } from '@testing-library/react';
import '@testing-library/jest-dom';
import { ChakraProvider } from '@chakra-ui/react';
import { HyperglassContext } from '~/context';
import { BGPTable } from './bgp-table';

import type { Config } from '~/types';

const config = {
  parsedDataFields: [
    ['Prefix', 'prefix', 'left'],
    ['AS Path', 'as_path', 'left'],
  ],
  web: { text: {} },
} as unknown as Config;

const route = {
  prefix: '1.0.0.0/24',
  active: true,
  age: 60,
  weight: 0,
  med: 0,
  local_preference: 100,
  as_path: [65000, 64999, 13335],
  communities: [],
  next_hop: '192.0.2.1',
  source_as: 13335,
  source_rid: '',
  peer_rid: '',
  rpki_state: 1,
};

function output(asnOrganizations: Record<string, { name: string }>): StructuredResponse {
  return {
    vrf: 'default',
    count: 1,
    routes: [route],
    winning_weight: 'high',
    asn_organizations: asnOrganizations,
  } as unknown as StructuredResponse;
}

function wrap(data: StructuredResponse): JSX.Element {
  return (
    <ChakraProvider>
      <HyperglassContext.Provider value={config}>
        <BGPTable>{data}</BGPTable>
      </HyperglassContext.Provider>
    </ChakraProvider>
  );
}

beforeAll(() => {
  // jsdom has no matchMedia; Chakra's responsive hooks need it.
  vi.stubGlobal(
    'matchMedia',
    vi.fn((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
    })),
  );
});

describe('BGPTable', () => {
  it('updates cells in place when async enrichment replaces the output (#86)', () => {
    const { container, rerender } = render(wrap(output({})));
    const link = () => container.querySelector('a[href="https://bgp.tools/as/13335"]');
    const before = link();
    expect(before).not.toBeNull();

    rerender(wrap(output({ '13335': { name: 'Cloudflare, Inc.' } })));

    // A remount would replace the node, and with it any open tooltip.
    expect(link()).toBe(before);
  });
});
