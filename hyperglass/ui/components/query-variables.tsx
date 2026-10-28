import { Select } from '~/components';
import { isSingleValue } from '~/components/select';
import { useFormState } from '~/hooks';

import type { SelectOnChange } from '~/components/select';
import type { DirectiveVariable, SingleOption } from '~/types';

interface QueryVariableProps {
  variable: DirectiveVariable;
  onChange(id: string, value: string | null): void;
}

export const QueryVariable = (props: QueryVariableProps): JSX.Element => {
  const { variable, onChange } = props;
  const selected = useFormState(s => s.form.queryVariables[variable.id] ?? null);

  const options: SingleOption[] = variable.options.map(o => ({ value: o.value, label: o.name }));
  const value = options.find(o => o.value === selected) ?? null;

  const handleChange: SelectOnChange<SingleOption> = e => {
    onChange(variable.id, isSingleValue(e) ? e.value : null);
  };

  return (
    <Select<SingleOption, false>
      name={`queryVariables.${variable.id}`}
      options={options}
      value={value}
      isClearable={!variable.required}
      onChange={handleChange}
    />
  );
};
