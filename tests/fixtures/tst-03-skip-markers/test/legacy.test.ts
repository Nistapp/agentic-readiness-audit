import { describe, it } from 'vitest';

describe('legacy', () => {
  it.skip('is skipped', () => {});
  it.todo('is a todo');
  xit('is an old-style skip', () => {});
});
