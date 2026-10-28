import { useQuery } from '@tanstack/react-query';
import { useConfig } from '~/context';
import { fetchWithTimeout } from '~/util';

import type {
  QueryFunction,
  UseQueryResult,
  UseQueryOptions,
  QueryFunctionContext,
} from '@tanstack/react-query';

interface WtfIndividual {
  ip: string;
  isp: string;
  location: string;
  country: string;
}

type Wtf = [UseQueryResult<WtfIndividual>, UseQueryResult<WtfIndividual>, () => Promise<void>];

/**
 * myip.wtf response.
 *
 * @see https://github.com/wtfismyip/wtfismyip
 * @see https://wtfismyip.com/automation
 */
interface WtfIsMyIP {
  YourFuckingIPAddress: string;
  YourFuckingLocation: string;
  YourFuckingISP: string;
  YourFuckingTorExit: boolean;
  YourFuckingCountryCode: string;
}

const URL_IP4 = 'https://ipv4.json.myip.wtf';
const URL_IP6 = 'https://ipv6.json.myip.wtf';

// In `server` mode, Ultraglass returns the address it received the request from.
const SERVER_IP4 = '/api/myip?family=4';
const SERVER_IP6 = '/api/myip?family=6';

function transform(wtf: WtfIsMyIP | { ip: string }): WtfIndividual {
  if ('ip' in wtf) {
    return { ip: wtf.ip, isp: '', location: '', country: '' };
  }
  const { YourFuckingIPAddress, YourFuckingISP, YourFuckingLocation, YourFuckingCountryCode } = wtf;
  return {
    ip: YourFuckingIPAddress,
    isp: YourFuckingISP,
    location: YourFuckingLocation,
    country: YourFuckingCountryCode,
  };
}

async function lookup(url: string): Promise<WtfIndividual> {
  const res = await fetchWithTimeout(
    url,
    {
      headers: { accept: 'application/json' },
      mode: 'cors',
    },
    5000,
    new AbortController(),
  );
  if (!res.ok) {
    throw new Error(`${url} returned ${res.status}`);
  }
  return transform(await res.json());
}

/**
 * Look up the address at `url`. If that fails and a fallback is given, ask the fallback.
 *
 * In `external` mode the fallback is the server endpoint for the same family, so a blocked
 * or failed myip.wtf lookup still returns the address Ultraglass sees.
 */
export async function lookupAddress(url: string, fallback?: string): Promise<WtfIndividual> {
  try {
    return await lookup(url);
  } catch (error) {
    if (fallback === undefined) {
      throw error;
    }
    return await lookup(fallback);
  }
}

const query: QueryFunction<WtfIndividual, string[]> = async (
  ctx: QueryFunctionContext<string[]>,
) => {
  const [url, fallback] = ctx.queryKey;
  return await lookupAddress(url, fallback);
};

const common: UseQueryOptions<WtfIndividual, unknown, WtfIndividual, string[]> = {
  queryFn: query,
  enabled: false,
  refetchInterval: false,
  refetchOnMount: false,
  refetchOnReconnect: false,
  refetchOnWindowFocus: false,
  cacheTime: 120 * 1_000, // 2 minutes
};

export function useWtf(): Wtf {
  const { web } = useConfig();
  const server = web.myIp === 'server';
  // `external` falls back to the server endpoint when myip.wtf fails.
  const ipv4 = useQuery<WtfIndividual, unknown, WtfIndividual, string[]>({
    queryKey: server ? [SERVER_IP4] : [URL_IP4, SERVER_IP4],
    ...common,
  });
  const ipv6 = useQuery<WtfIndividual, unknown, WtfIndividual, string[]>({
    queryKey: server ? [SERVER_IP6] : [URL_IP6, SERVER_IP6],
    ...common,
  });

  async function refetch(): Promise<void> {
    await ipv4.refetch();
    await ipv6.refetch();
  }
  return [ipv4, ipv6, refetch];
}
