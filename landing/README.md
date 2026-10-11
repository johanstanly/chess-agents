# The front page (landing page)

The site's front page: Magnus introduces the project over a video of the monitor man, who turns his head
towards the mouse. Rules from Magnus's notebook fade in one after another above the typed introduction.

Built with React, TypeScript, Vite and Tailwind CSS. Node.js is needed only to change this page; the rest
of the site (results, replays, 3D view) is plain HTML in `docs/`.

```
npm install        # once
npm run dev        # preview while editing: http://127.0.0.1:5174/
npm run build      # writes the page into ../docs (index.html, landing/, hero.mp4, knight.svg)
```

After `npm run build`, commit the changed files in `docs/` to publish.

- The words, links and notebook rules are at the top of `src/App.tsx`.
- `public/hero.mp4` is the template's video re-encoded at 1080p with every frame a keyframe, so the head can
  turn smoothly (jumping to any frame is instant).
