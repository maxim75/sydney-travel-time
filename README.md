# Sydney travel times

Public transport travel times across Greater Sydney, shown as a hexagon map at
https://maxim75.github.io/sydney-travel-time/.

- Python (`uv`) collects journeys and builds the map data: `uv run build_travel_time_map.py`
  writes `web/public/site.json` and `web/public/map_data/`.
- `web/` is a Next.js + TypeScript app exported as a static site (Node 20.9 or newer). To publish:

  ```bash
  cd web && npm install && npm run publish-site
  ```

  This replaces `docs/`, which GitHub Pages serves from the `main` branch. Commit `docs/` to publish.
- Develop with `npm run dev` in `web/`, then open http://localhost:3000/sydney-travel-time/. Tests: `npm test`, `npm run test:e2e`.
- The Python build needs the git-ignored `data/` inputs. For front-end-only work on a fresh clone, copy
  `docs/site.json` and `docs/map_data/` into `web/public/` instead.
