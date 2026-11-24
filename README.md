# mongory-spec

[![Spec Version](https://img.shields.io/github/v/tag/mongoryhq/mongory-spec?label=spec)](https://github.com/mongoryhq/mongory-spec/tags)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Cross-language conformance test specifications for **Mongory** implementations (`mongory-rb`, `mongory-core`, `mongory-go`, `mongory-js`, `mongory-py`).

Current Spec Version: **`0.2.1`** (see [`VERSION`](./VERSION))

---

## 1. Directory Structure

```text
mongory-spec/
├── README.md                        # Specification & integration guide
├── VERSION                          # Semantic version of the specification
├── schema.json                      # JSON Schema (Draft 2020-12) for fixture files
└── fixtures/
    ├── field/
    │   ├── basic_and_nested.json    # Empty condition, 1-layer & deep nested field matching
    │   └── dot_and_index_keys.json  # Dot notation, escaped dot (\.), array index keys (0, -1, 01, -0)
    ├── compare/
    │   ├── eq_ne.json               # $eq, $ne (scalars, int/float cross-type, null, objects, arrays)
    │   └── gt_gte_lt_lte.json       # $gt, $gte, $lt, $lte (numeric, string, incomparable types)
    ├── inclusion/
    │   └── in_nin.json              # $in, $nin (scalars, array intersection semantics, null)
    ├── existence/
    │   └── exists_present.json      # $exists, $present (missing key vs null vs empty values)
    ├── composite/
    │   ├── and.json                 # $and (top-level & field-level)
    │   ├── or.json                  # $or (top-level & field-level)
    │   └── not.json                 # $not (negation of subconditions)
    ├── array/
    │   ├── implicit_array.json      # MongoDB-aligned implicit array matching (scalar, range, $eq/$ne, object array)
    │   ├── elem_match.json          # $elemMatch
    │   ├── every.json               # $every
    │   └── size.json                # $size (exact integer & nested range operators)
    ├── regex/
    │   ├── regex.json               # $regex (cross-engine common regex subset)
    │   └── options.json             # $regex with $options (i, m, s)
    └── errors/
        ├── invalid_conditions.json  # Invalid operator conditions ("error": true)
        └── unknown_operators.json   # Unknown "$" operators and misplaced $options ("error": true)
```

---

## 2. Fixture Format

Every `.json` file under `fixtures/` is a JSON array of test suites conforming to [`schema.json`](./schema.json).

### 2.1 Normal Match Suite

```json
{
  "description": "operator $gt basic comparison",
  "condition": {
    "age": { "$gt": 30 }
  },
  "records": [
    { "data": { "age": 40 }, "expected": true },
    { "data": { "age": 30 }, "expected": false },
    { "data": { "age": null }, "expected": false }
  ]
}
```

- **`condition`** is **always a JSON Object** (`{ ... }`), representing a top-level Mongory query document.
- **`records`** is a list of `{ "data": <any JSON value>, "expected": <boolean> }` pairs.

### 2.2 Error Validation Suite

```json
{
  "description": "$in with non-array condition raises error",
  "condition": {
    "age": { "$in": 123 }
  },
  "error": true
}
```

- When **`"error": true`** is set, compiling/validating `condition` MUST fail with an error/exception.

---

## 3. Core Semantic Rules

### 3.1 Field Lookup & Key Resolution
1. **Dot Notation (Binding Responsibility)**:
   - A field key containing unescaped `.` (e.g., `"a.b.c": 10`) traverses nested objects/arrays (`{ "a": { "b": { "c": 10 } } }`), and overlapping dotted prefixes deep-merge (`{ "a.b": 1, "a.c": 2 }` → `{ "a": { "b": 1, "c": 2 } }`).
   - Expanding dotted keys and unescaping `\.` is the responsibility of each **language binding / condition normalizer** (e.g., `mongory-rb`'s `ConditionConverter`/`KeyConverter`, `mongory-go`'s condition normalizer) before building the matcher tree, rather than `mongory-core` itself.
2. **Escaped Dots (Binding Responsibility)**:
   - `\.` in a field key is unescaped to a literal `.` without splitting (e.g., `"a\\.b.c"` expands to `{ "a.b": { "c": ... } }` and looks up literal key `"a.b"`).
3. **Array Index Keys**:
   - Canonical base-10 integer keys (`"0"`, `"1"`, `"-1"`, etc.) index into arrays (`0`-based from start, negative from end) **or** match string/integer keys on objects.
   - Leading-zero keys (`"01"`), negative zero (`"-0"`), or non-integer strings are **never** treated as array indices; on an array, they are treated as element sub-field lookups.
4. **Missing Key vs `null`**:
   - Accessing a missing key yields a distinct `MISSING` (`NOTHING`) sentinel for `$exists`, whereas an explicit `null` value has `$exists: true`.
   - For literal `null` condition (`{ "a": null }`), both a missing key (`{}`) and an explicit `null` value (`{ "a": null }`) match (emulating MongoDB `{ a: null }` via `$exists: false OR $eq: null`).
   - For explicit `$eq: null` (`{ "a": { "$eq": null } }`), only an explicit `null` value (`{ "a": null }`) matches; a missing key (`{}`) does not match.

### 3.2 Value Comparison (`$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`)
1. **Numeric Widening**: Integers (`int64`) and floating-point numbers (`float64`) are mutually comparable (`30 == 30.0`, `30 < 30.5`).
2. **Strings**: Compared lexicographically by UTF-8 byte order (`$gt`, `$gte`, `$lt`, `$lte`, `$eq`, `$ne`).
3. **Incomparable Types**: Comparing values of incompatible types (e.g., `string` vs `number`, `null` vs `number`, `boolean` vs `number`) returns `false` for `$gt`, `$gte`, `$lt`, `$lte`, and `$eq`, and `true` for `$ne`.
4. **Object Equality**: Two objects (`table` / `map`) are equal iff they have the exact same number of keys and every key's value is recursively equal (key order independent).
5. **Array Equality**: Two arrays are equal iff they have the exact same length and each element at index `i` is recursively equal (order sensitive).

### 3.3 MongoDB-Aligned Array Field Semantics
When a field's value in a record is an **Array**:
1. **Implicit Scalar Condition** (`{ "tags": "ruby" }`): Matches if `"ruby"` is an element of `tags`.
2. **Implicit Array Condition** (`{ "tags": ["go", "ruby"] }`): Matches if `tags` equals `["go", "ruby"]` as a whole array **OR** contains `["go", "ruby"]` as a nested array element.
3. **Implicit Operator / Sub-document Condition** (`{ "scores": { "$gt": 5, "$lt": 8 } }` or `{ "people": { "name": "Billy", "age": 18 } }`):
   - Array-level operators (`$elemMatch`, `$every`, `$size`, `$in`, `$nin`, `$not`, `$and`, `$or`, `$exists`, `$present`) and integer index keys (`"0"`, `"-1"`) apply to the array as a whole.
   - Comparison operators (`$gt`, `$gte`, `$lt`, `$lte`), `$regex`, scalar `$eq`, and sub-field conditions are grouped into an implicit **`$elemMatch`** (a single element in the array must satisfy all grouped conditions simultaneously).
4. **Explicit `$eq` and `$ne` on Array Values**:
   - `$eq` matches if the array itself equals the target value **OR** any element in the array equals the target value.
   - `$ne` is the strict negation of `$eq`: it returns `false` if the array itself equals the target value **OR** any element in the array equals the target value; otherwise `true`.

### 3.4 Official Cross-Engine Regex Subset (`$regex`)
To guarantee identical behavior across **RE2** (Go), **PCRE2** (C), **Oniguruma** (Ruby), and **ECMA-262 RegExp** (JS), `mongory-spec` restricts `$regex` patterns to the common regular expression subset:
- **Supported**:
  - Anchors: `^`, `$`
  - Character classes: `.`, `[abc]`, `[^abc]`, `[a-z]`, `\d`, `\D`, `\w`, `\W`, `\s`, `\S`
  - Quantifiers: `*`, `+`, `?`, `{n}`, `{n,}`, `{n,m}` (greedy and non-greedy `*?`, `+?`, `??`)
  - Grouping & alternation: `( ... )`, `(?: ... )`, `a|b`
  - Escaped metacharacters: `\.`, `\[`, `\\`, etc.
- **Excluded from cross-language spec** (engine-specific extensions):
  - Backreferences (`\1`, `\k<name>`)
  - Lookaround assertions (`(?=...)`, `(?!...)`, `(?<=...)`, `(?<!...)`)
  - Atomic groups / possessive quantifiers (`(?>...)`, `++`)
  - Conditional patterns and recursion

### 3.5 Regex Options (`$options`)
`$options` is a sibling key of `$regex` in the same condition object (`{ "$regex": "^ab", "$options": "i" }`), as in MongoDB. It is a string of flags:
- `i`: case-insensitive matching.
- `m`: `^` and `$` also match at line boundaries.
- `s`: `.` also matches a newline.

Compiling a condition MUST fail when:
- `$options` is not a string, or contains a flag other than `i`, `m`, `s` (MongoDB's `x` and `u` are not in the cross-engine subset).
- `$options` appears without a sibling `$regex`.

On an array field, `$options` travels with `$regex` into the implicit `$elemMatch` (see 3.3).

Anchor behavior on strings containing newlines **without** `m` is engine-dependent (Ruby's `^`/`$` always match at line boundaries) and is not covered by the spec.

### 3.6 Operator Validation
A condition key that starts with `$` and is not a supported operator MUST fail compilation, as MongoDB rejects unknown operators. This applies at any depth, including keys produced by dot-notation expansion (`"age.$foo"` expands to `{ "age": { "$foo": ... } }`). A key with `$` anywhere else (`"price$"`) is a regular field name.

### 3.7 Differences from MongoDB Query Syntax
Mongory is **MongoDB-inspired** for in-memory rule evaluation and differs intentionally from MongoDB Server in the following areas:

| Area | Mongory Behavior | MongoDB Server Behavior |
|------|-----------------|-------------------------|
| **`$every`** | Built-in array quantifier; requires **all** elements to match and returns `false` on empty arrays `[]` (no vacuous truth). | Not a native query operator (requires `$not` + `$elemMatch` or `$expr`/`$allElementsTrue`). |
| **`$present`** | Built-in presence check (ActiveSupport-style): `false` for missing key, `null`, `false`, `""`, `[]`, and `{}`; `true` for numbers (including `0`) and non-empty strings/arrays/objects. | Not a native operator. |
| **`$regex` / `$options`** | Restricted to the cross-engine regex subset (`^`, `$`, character classes, quantifiers, alternation/groups) and flags `i`, `m`, `s`. | Supports full PCRE2 extensions and additional flags such as `x` and `u`. |
| **Operators outside the 17** | Unknown `$`-prefixed keys fail compilation. Aggregation (`$expr`), bitwise, geospatial, `$type`, `$mod`, `$text`, and update operators are excluded. | Supported in MongoDB query/aggregation pipelines. |
| **In-memory evaluation extensions** | Supports priority-sorted sibling short-circuiting with dynamic re-sorting on lazy array matching, plus `explain` / `trace` debugging. | Query planner uses B-tree indexes / collection scans on persisted documents. |

---

## 4. Integrating via Git Submodule

```bash
git submodule add https://github.com/mongoryhq/mongory-spec.git spec
```

### Conformance Runner Pseudocode

```python
for file in glob("spec/fixtures/**/*.json"):
    suites = json.parse(read(file))
    for suite in suites:
        if suite.get("error") is True:
            assert_raises(lambda: Mongory.compile(suite["condition"]))
        else:
            matcher = Mongory.compile(suite["condition"])
            for record in suite["records"]:
                assert matcher.match(record["data"]) == record["expected"], \
                    f"{file}: {suite['description']} failed on {record['data']}"
```
