# Sydney travel times

Public transport travel times across Greater Sydney, shown as a hexagon map at
https://maxim75.github.io/sydney-travel-time/.

- Python (`uv`) collects journeys and builds the map data: `uv run build_travel_time_map.py`
  writes `web/public/site.json` and `web/public/map_data/`.
- `web/` is a Next.js + TypeScript app exported as a static site. To publish:

```bash
cd web && npm install && npm run publish-site
```

  This replaces `docs/`, which GitHub Pages serves from the `main` branch. Commit `docs/` to publish.
- Develop with `npm run dev` in `web/`, then open http://localhost:3000/sydney-travel-time/. Tests: `npm test`, `npm run test:e2e`.
