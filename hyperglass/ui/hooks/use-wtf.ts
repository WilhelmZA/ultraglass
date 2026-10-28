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

const query: QueryFunction<WtfIndividual, string[]> = async (
  ctx: QueryFunctionContext<string[]>,
) => {
  const controller = new AbortController();
  const [url] = ctx.queryKey;

  const res = await fetchWithTimeout(
    url,
    {
      headers: { accept: 'application/json' },
      mode: 'cors',
    },
    5000,
    controller,
  );
  const data = await res.json();
  return transform(data);
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
  const ipv4 = useQuery<WtfIndividual, unknown, WtfIndividual, string[]>({
    queryKey: [server ? SERVER_IP4 : URL_IP4],
    ...common,
  });
  const ipv6 = useQuery<WtfIndividual, unknown, WtfIndividual, string[]>({
    queryKey: [server ? SERVER_IP6 : URL_IP6],
    ...common,
  });

  async function refetch(): Promise<void> {
    await ipv4.refetch();
    await ipv6.refetch();
  }
  return [ipv4, ipv6, refetch];
}
