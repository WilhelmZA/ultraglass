import { createContext, useContext } from 'react';
import { Flex } from '@chakra-ui/react';
import { Table } from '~/components';
import { useConfig } from '~/context';
import { Cell } from './cell';

import type { FlexProps } from '@chakra-ui/react';
import type { TableColumn, ParsedDataField, CellRenderProps } from '~/types';

type BGPTableProps = Swap<FlexProps, 'children', StructuredResponse>;

function makeColumns(fields: ParsedDataField[]): TableColumn[] {
  return fields.map(pair => {
    const [header, accessor, align] = pair;

    const columnConfig = {
      align,
      accessor,
      hidden: false,
      Header: header,
    } as TableColumn;

    if (align === null) {
      columnConfig.hidden = true;
    }

    return columnConfig;
  });
}

// The table renders `Cell` as a component, so it must keep one identity across renders.
// An inline renderer is a new component type on every render: when async enrichment
// replaces the output, every cell remounts and an open AS path tooltip closes (#86).
// The current response reaches the stable renderer through context instead.
const BGPTableData = createContext<StructuredResponse | null>(null);

const BGPTableCell = (props: CellRenderProps): JSX.Element | null => {
  const data = useContext(BGPTableData);
  return data === null ? null : <Cell data={props} rawData={data} />;
};

export const BGPTable = (props: BGPTableProps): JSX.Element => {
  const { children: data, ...rest } = props;
  const { parsedDataFields } = useConfig();
  const columns = makeColumns(parsedDataFields);

  return (
    <Flex my={8} justify="center" maxW="100%" w="100%" {...rest}>
      <BGPTableData.Provider value={data}>
        <Table
          columns={columns}
          bordersHorizontal
          data={data.routes}
          rowHighlightBg="green"
          rowHighlightProp="active"
          Cell={BGPTableCell}
        />
      </BGPTableData.Provider>
    </Flex>
  );
};
