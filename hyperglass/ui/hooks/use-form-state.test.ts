import { expect, test } from 'vitest';
import { useFormState } from './use-form-state';

test('back - returns to the form and keeps the last query', () => {
  const form = {
    queryLocation: ['lab-frr'],
    queryTarget: ['1.1.1.1'],
    queryType: 'bgp_route',
    queryVariables: { group: 'party_x' },
  };
  useFormState.setState({ form, status: 'results', target: { display: '1.1.1.1' } });

  useFormState.getState().back();

  const state = useFormState.getState();
  expect(state.status).toBe('form');
  expect(state.form).toEqual(form);
  expect(state.target.display).toBe('1.1.1.1');
});

test('reset - clears the last query', async () => {
  await useFormState.getState().reset();

  expect(useFormState.getState().form.queryLocation).toEqual([]);
  expect(useFormState.getState().form.queryVariables).toEqual({});
});
