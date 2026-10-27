import assert from 'node:assert/strict';
import test from 'node:test';
import { isIdTokenExpired } from '../lib/tokenExpiry.ts';

const now = 1_800_000_000;

test('accepts an ID token with over 60 seconds remaining', () => {
  assert.equal(isIdTokenExpired(now + 3600, now), false);
});
test('rejects expired or nearly expired ID tokens', () => {
  assert.equal(isIdTokenExpired(now - 1, now), true);
  assert.equal(isIdTokenExpired(now + 60, now), true);
  assert.equal(isIdTokenExpired(now + 61, now), false);
});
test('rejects unknown or invalid expiration claims', () => {
  for (const exp of [null, undefined, '1800000000', NaN, Infinity]) {
    assert.equal(isIdTokenExpired(exp, now), true);
  }
});
