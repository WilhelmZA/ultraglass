import { afterEach, describe, expect, it, vi } from 'vitest';
import { lookupAddress } from './use-wtf';

const EXTERNAL = 'https://ipv4.json.myip.wtf';
const SERVER = '/api/myip?family=4';

function respond(body: unknown, ok = true): Response {
  return { ok, status: ok ? 200 : 503, json: async () => body } as Response;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('lookupAddress', () => {
  it('uses the external answer when it succeeds', async () => {
    const fetchMock = vi.fn(async () =>
      respond({
        YourFuckingIPAddress: '192.0.2.1',
        YourFuckingISP: 'Example',
        YourFuckingLocation: 'Johannesburg',
        YourFuckingCountryCode: 'ZA',
      }),
    );
    vi.stubGlobal('fetch', fetchMock);
    const result = await lookupAddress(EXTERNAL, SERVER);
    expect(result.ip).toBe('192.0.2.1');
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('falls back to the server when the external lookup fails', async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url === EXTERNAL) {
        throw new TypeError('Failed to fetch');
      }
      return respond({ ip: '198.51.100.7' });
    });
    vi.stubGlobal('fetch', fetchMock);
    const result = await lookupAddress(EXTERNAL, SERVER);
    expect(result.ip).toBe('198.51.100.7');
    expect(fetchMock.mock.calls.map(call => call[0])).toEqual([EXTERNAL, SERVER]);
  });

  it('falls back to the server when the external lookup returns an error status', async () => {
    const fetchMock = vi.fn(async (url: string) =>
      url === EXTERNAL ? respond({}, false) : respond({ ip: '198.51.100.7' }),
    );
    vi.stubGlobal('fetch', fetchMock);
    expect((await lookupAddress(EXTERNAL, SERVER)).ip).toBe('198.51.100.7');
  });

  it('fails without a fallback', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch');
      }),
    );
    await expect(lookupAddress(SERVER)).rejects.toThrow('Failed to fetch');
  });
});
