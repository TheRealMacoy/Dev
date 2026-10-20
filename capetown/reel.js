// Orbit-to-Cape-Town reel. Every frame is a pure function of its index, so
// frames render out of order across parallel browsers.
//
// 0–6s orbit around the night side into an orbital sunrise over Africa
// 6–7s target lock on Cape Town
// 7–13s spiralling descent: globe → Sentinel-2 imagery → 3D terrain, landing
//        at the drone's real position over Green Point
// 13s+  cross-dissolve into the drone footage with tracked motion graphics
import * as THREE from 'three';

const W = 1920, H = 1080, FPS = 60;
const R = 6371; // km
const D2R = Math.PI / 180;
const T_VIDEO = 13.0, VIDEO_FRAMES = 330, VIDEO_FPS = 30000 / 1001;
const DUR = T_VIDEO + VIDEO_FRAMES / VIDEO_FPS;
window.TOTAL_FRAMES = Math.floor(DUR * FPS);

const CPT = { lat: -33.9249, lon: 18.4241 };
const SUN = { lat: -8, lon: 30 };
// Drone pose solved from landmark bearings in the first video frame
const DRONE = { lat: -33.8865, lon: 18.4035, alt: 0.54, heading: 168.75, tilt: 82.3, vfov: 43 };

const C = { white: '#FFFFFF', cyan: '#7FE7FF', amber: '#FFB23F' };
const DISP = '"Inter Display", Inter, sans-serif';
const MONO = '"JetBrains Mono", monospace';

// ---------- math helpers ----------
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, t) => a + (b - a) * t;
const prog = (t, a, b) => clamp((t - a) / (b - a));
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a)); return t * t * (3 - 2 * t); };
const E = {
  outExpo: t => t >= 1 ? 1 : 1 - Math.pow(2, -10 * t),
  inOutCubic: t => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2,
  inOutSine: t => -(Math.cos(Math.PI * t) - 1) / 2,
  outCubic: t => 1 - Math.pow(1 - t, 3),
  inCubic: t => t * t * t,
  outBack: t => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2); },
};
function rng(seed) {
  return () => {
    seed = seed + 0x6D2B79F5 | 0;
    let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}

// ECEF in km; matches three's SphereGeometry uv layout (lon 0 at +x, north at +y)
function ecef(lat, lon, h = 0) {
  const p = lat * D2R, l = lon * D2R, r = R + h;
  return new THREE.Vector3(r * Math.cos(p) * Math.cos(l), r * Math.sin(p), -r * Math.cos(p) * Math.sin(l));
}
function enu(lat, lon) {
  const p = lat * D2R, l = lon * D2R;
  return {
    up: new THREE.Vector3(Math.cos(p) * Math.cos(l), Math.sin(p), -Math.cos(p) * Math.sin(l)),
    east: new THREE.Vector3(-Math.sin(l), 0, -Math.cos(l)),
    north: new THREE.Vector3(-Math.sin(p) * Math.cos(l), Math.cos(p), Math.sin(p) * Math.sin(l)),
  };
}
function toLatLon(v) {
  const n = v.clone().normalize();
  return { lat: Math.asin(n.y) / D2R, lon: Math.atan2(-n.z, n.x) / D2R };
}

// ---------- camera choreography ----------
const FINAL = (() => {
  const d = DRONE.alt * Math.tan(DRONE.tilt * D2R);
  const dn = d * Math.cos(DRONE.heading * D2R), de = d * Math.sin(DRONE.heading * D2R);
  return {
    lat: DRONE.lat + dn / 111.19, lon: DRONE.lon + de / (111.19 * Math.cos(DRONE.lat * D2R)),
    range: Math.hypot(d, DRONE.alt),
  };
})();
const LOG = Math.log;
function camState(t) {
  // orbit: from the anti-sun point, across the night side into the sunrise
  const o = E.inOutCubic(prog(t, 0.3, 6.2));
  let lat = lerp(14, CPT.lat, E.inOutSine(prog(t, 1.0, 6.2)));
  let lon = lerp(-152, CPT.lon, o);
  let logR;
  if (t < 6.2) logR = lerp(LOG(24000), LOG(15500), E.inOutSine(prog(t, 0, 6.2)));
  else logR = lerp(LOG(15500), LOG(FINAL.range), descentCurve(prog(t, 6.2, 13.0)));
  const range = Math.exp(logR);
  // slide the aim point to the drone's target as we get low
  const w = smooth(LOG(400), LOG(12), logR);
  if (t >= 6.2) { lat = lerp(CPT.lat, FINAL.lat, w); lon = lerp(CPT.lon, FINAL.lon, w); }
  const heading = DRONE.heading * E.inOutCubic(prog(t, 7.0, 12.6));
  const tilt = DRONE.tilt * Math.pow(smooth(LOG(140), LOG(FINAL.range), logR), 1.35);
  const vfov = lerp(30, DRONE.vfov, smooth(LOG(60), LOG(FINAL.range), logR));
  const offY = -360 * (1 - E.inOutCubic(prog(t, 0, 5.2)));
  return { lat, lon, range, heading, tilt, vfov, offY };
}
// slow start (the lock hold), long dive, gentle settle at the drone's position
function descentCurve(p) {
  const a = 0.13;
  if (p < a) return 0.035 * E.inCubic(p / a) * 1;
  const q = (p - a) / (1 - a);
  return 0.035 + 0.965 * (1 - Math.pow(1 - E.inOutSine(q), 1.6));
}

function applyCamera(cam, s) {
  const { up, east, north } = enu(s.lat, s.lon);
  const hd = s.heading * D2R, tl = s.tilt * D2R;
  const fwdH = north.clone().multiplyScalar(Math.cos(hd)).add(east.clone().multiplyScalar(Math.sin(hd)));
  const view = up.clone().multiplyScalar(-Math.cos(tl)).add(fwdH.clone().multiplyScalar(Math.sin(tl)));
  const target = ecef(s.lat, s.lon, 0);
  const pos = target.clone().sub(view.clone().multiplyScalar(s.range));
  cam.position.copy(pos);
  cam.up.copy(fwdH.clone().multiplyScalar(Math.cos(tl)).add(up.clone().multiplyScalar(Math.sin(tl))));
  cam.lookAt(target);
  cam.fov = s.vfov;
  cam.near = Math.max(0.005, (pos.length() - R - 1.2) * 0.5);
  cam.far = 4e6;
  cam.setViewOffset(W, H, 0, s.offY, W, H);
  cam.updateProjectionMatrix();
  cam.updateMatrixWorld();
  return { pos, target, alt: pos.length() - R };
}

// ---------- three.js scene ----------
const renderer = new THREE.WebGLRenderer({
  canvas: document.getElementById('gl'), antialias: true, logarithmicDepthBuffer: true, preserveDrawingBuffer: true,
});
renderer.setPixelRatio(1);
renderer.setSize(W, H, false);
renderer.outputColorSpace = THREE.LinearSRGBColorSpace;
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(30, W / H, 1, 4e6);
const sunDir = ecef(SUN.lat, SUN.lon).normalize();

const hud = document.getElementById('hud');
const ctx = hud.getContext('2d');

let meta, globe, atmo, stars, city, videoTracks;
const grain = [], puffs = [];

function loadTex(url) {
  return new Promise((res, rej) => new THREE.TextureLoader().load(url, t => {
    t.colorSpace = THREE.NoColorSpace;
    t.anisotropy = renderer.capabilities.getMaxAnisotropy();
    t.generateMipmaps = true;
    t.minFilter = THREE.LinearMipmapLinearFilter;
    res(t);
  }, undefined, rej));
}

const SHARED_GLSL = /* glsl */`
  uniform vec3 sunDir;
  uniform vec4 regBox; uniform vec4 cityBox;
  uniform sampler2D regTex; uniform sampler2D cityTex;
  uniform float hazeAmt; uniform float visibility; uniform float hazeDay;
  vec3 enrichWater(vec3 c) {
    float lum = dot(c, vec3(.299, .587, .114));
    float w = smoothstep(.13, .04, lum) * smoothstep(-.01, .03, c.b - c.r);
    return mix(c, vec3(.05, .19, .33) + c * .7, w);
  }
  vec4 patchColor(float lat, float lon, inout vec3 base) {
    vec2 ruv = vec2((lon - regBox.x) / (regBox.y - regBox.x), (lat - regBox.z) / (regBox.w - regBox.z));
    float inside = 0.0;
    if (all(greaterThan(ruv, vec2(0.))) && all(lessThan(ruv, vec2(1.)))) {
      vec4 r = texture2D(regTex, ruv);
      base = mix(base, enrichWater(r.rgb), r.a);
      inside = r.a;
    }
    vec2 cuv = vec2((lon - cityBox.x) / (cityBox.y - cityBox.x), (lat - cityBox.z) / (cityBox.w - cityBox.z));
    if (all(greaterThan(cuv, vec2(0.))) && all(lessThan(cuv, vec2(1.)))) {
      vec4 c = texture2D(cityTex, cuv);
      base = mix(base, enrichWater(c.rgb), c.a);
    }
    return vec4(cuv, inside, 0.);
  }
  vec3 haze(vec3 col, vec3 wpos, float lit) {
    float d = length(cameraPosition - wpos);
    float h = (1. - exp(-d / visibility)) * hazeAmt;
    vec3 hc = mix(vec3(.07, .1, .16), vec3(.62, .76, .93), lit * hazeDay);
    return mix(col, hc, h);
  }
`;

function makeGlobe(tex) {
  const mat = new THREE.ShaderMaterial({
    uniforms: {
      dayTex: { value: tex.day }, nightTex: { value: tex.night }, bumpTex: { value: tex.bump },
      regTex: { value: tex.reg }, cityTex: { value: tex.city },
      regBox: { value: new THREE.Vector4(...meta.regional) }, cityBox: { value: new THREE.Vector4(...meta.city) },
      sunDir: { value: sunDir }, cloudShift: { value: 0 }, cloudAmt: { value: 1 }, gridAmt: { value: 0 },
      holeAmt: { value: 0 }, hazeAmt: { value: 0 }, visibility: { value: 80 }, hazeDay: { value: 1 },
    },
    vertexShader: /* glsl */`
      #include <common>
      #include <logdepthbuf_pars_vertex>
      varying vec2 vUv; varying vec3 vPos;
      void main() {
        vUv = uv;
        vec4 wp = modelMatrix * vec4(position, 1.0);
        vPos = wp.xyz;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        #include <logdepthbuf_vertex>
      }`,
    fragmentShader: /* glsl */`
      #include <common>
      #include <logdepthbuf_pars_fragment>
      uniform sampler2D dayTex, nightTex, bumpTex;
      uniform float cloudShift, cloudAmt, gridAmt, holeAmt;
      varying vec2 vUv; varying vec3 vPos;
      ${SHARED_GLSL}
      float gridLine(float v, float step) {
        float f = abs(fract(v / step + .5) - .5) * step;
        return 1. - smoothstep(0., fwidth(v) * 1.2, f);
      }
      void main() {
        #include <logdepthbuf_fragment>
        vec3 n = normalize(vPos);
        float lat = degrees(asin(clamp(n.y, -1., 1.)));
        float lon = degrees(atan(-n.z, n.x));
        vec3 day = texture2D(dayTex, vUv).rgb;
        vec4 pc = patchColor(lat, lon, day);
        if (holeAmt > .5 && all(greaterThan(pc.xy, vec2(.006))) && all(lessThan(pc.xy, vec2(.994)))) discard;
        float ndl = dot(n, sunDir);
        float dayMask = smoothstep(-.12, .22, ndl);
        vec3 V = normalize(cameraPosition - vPos);
        vec3 col = day * (.035 + dayMask * (.62 + .5 * max(ndl, 0.)));
        vec4 bump = texture2D(bumpTex, vUv);
        float water = 1. - bump.g;
        float spec = pow(max(dot(reflect(-sunDir, n), V), 0.), 70.) * water * dayMask * (1. - pc.z);
        col += vec3(1., .93, .8) * spec * .75;
        vec3 lights = texture2D(nightTex, vUv).rgb;
        col += lights * lights * vec3(1.6, 1.15, .7) * (1. - smoothstep(-.18, .08, ndl));
        float cl = texture2D(bumpTex, vUv + vec2(cloudShift, 0.)).b;
        cl = smoothstep(.12, .85, cl) * cloudAmt * (1. - pc.z);
        col = mix(col, vec3(1.) * (.03 + .97 * dayMask) * (.8 + .2 * max(ndl, 0.)), cl * .92);
        float fres = pow(1. - max(dot(n, V), 0.), 3.);
        float litRim = smoothstep(-.35, .45, ndl);
        col += mix(vec3(1., .45, .2), vec3(.3, .6, 1.), smoothstep(-.1, .4, ndl)) * fres * litRim * .85;
        float g = max(gridLine(lat, 10.), gridLine(lon, 10.));
        col = mix(col, vec3(.5, .9, 1.), g * gridAmt * (.35 + .65 * dayMask));
        col = haze(col, vPos, dayMask);
        gl_FragColor = vec4(col, 1.);
      }`,
  });
  const m = new THREE.Mesh(new THREE.SphereGeometry(R, 1024, 512), mat);
  scene.add(m);
  return m;
}

function makeAtmosphere() {
  const mat = new THREE.ShaderMaterial({
    uniforms: { sunDir: { value: sunDir }, R: { value: R }, skyAmt: { value: 1 } },
    side: THREE.BackSide, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    vertexShader: /* glsl */`
      #include <common>
      #include <logdepthbuf_pars_vertex>
      varying vec3 vPos;
      void main() {
        vPos = (modelMatrix * vec4(position, 1.0)).xyz;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        #include <logdepthbuf_vertex>
      }`,
    fragmentShader: /* glsl */`
      #include <common>
      #include <logdepthbuf_pars_fragment>
      uniform vec3 sunDir; uniform float R; uniform float skyAmt;
      varying vec3 vPos;
      void main() {
        #include <logdepthbuf_fragment>
        vec3 ro = cameraPosition, rd = normalize(vPos - ro);
        float tca = -dot(ro, rd);
        vec3 pc = ro + rd * max(tca, 0.);
        float d = length(pc);
        float h = max(d - R, 0.);
        float g = exp(-h / 55.) * 1.15 + exp(-h / 14.) * .6;
        float lit = dot(normalize(pc), sunDir);
        vec3 dayc = vec3(.28, .55, 1.);
        vec3 col = mix(vec3(1., .5, .22), dayc, smoothstep(-.05, .45, lit)) * smoothstep(-.32, .08, lit);
        float fwd = pow(max(dot(rd, sunDir), 0.), 10.);
        col += vec3(1., .72, .45) * fwd * 1.6 * smoothstep(-.35, .05, lit);
        // inside the atmosphere: a deep blue zenith fading to pale horizon
        float alt = length(ro) - R;
        float inside = 1. - smoothstep(30., 160., alt);
        float up = dot(rd, normalize(ro));
        vec3 sky = mix(vec3(.62, .78, .95), vec3(.13, .38, .86), smoothstep(-.02, .35, up));
        col = mix(col * g, sky * smoothstep(-.06, .0, up + .05), inside * skyAmt);
        gl_FragColor = vec4(col, 1.);
      }`,
  });
  const m = new THREE.Mesh(new THREE.SphereGeometry(R * 1.035, 256, 128), mat);
  m.renderOrder = 2;
  scene.add(m);
  return m;
}

function makeStars() {
  const r = rng(11), n = 9000;
  const pos = new Float32Array(n * 3), size = new Float32Array(n), tint = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const u = r() * 2 - 1, th = r() * Math.PI * 2, s = Math.sqrt(1 - u * u);
    // a faint band of extra stars for a Milky Way
    let x = s * Math.cos(th), y = u, z = s * Math.sin(th);
    if (i < n * .35) { y = (r() - .5) * .25 + .3 * x; const l = Math.hypot(x, y, z); x /= l; y /= l; z /= l; }
    pos.set([x * 2e6, y * 2e6, z * 2e6], i * 3);
    size[i] = Math.pow(r(), 9) * 5.5 + .9;
    tint[i] = r();
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('size', new THREE.BufferAttribute(size, 1));
  g.setAttribute('tint', new THREE.BufferAttribute(tint, 1));
  const mat = new THREE.ShaderMaterial({
    uniforms: { amt: { value: 1 } }, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    vertexShader: /* glsl */`
      #include <common>
      #include <logdepthbuf_pars_vertex>
      attribute float size; attribute float tint; varying float vT;
      void main() { vT = tint; gl_PointSize = size; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.);
        #include <logdepthbuf_vertex>
      }`,
    fragmentShader: /* glsl */`
      #include <common>
      #include <logdepthbuf_pars_fragment>
      uniform float amt; varying float vT;
      void main() {
        #include <logdepthbuf_fragment>
        float d = length(gl_PointCoord - .5);
        float a = smoothstep(.5, 0., d);
        vec3 c = mix(vec3(.75, .85, 1.), vec3(1., .88, .72), vT);
        gl_FragColor = vec4(c * a * amt, 1.);
      }`,
  });
  const p = new THREE.Points(g, mat);
  p.renderOrder = -1;
  scene.add(p);
  return p;
}

async function makeCity(tex) {
  const { w, h } = meta.height;
  const hm = new Float32Array(await (await fetch('data/height_city.bin')).arrayBuffer());
  const [lon0, lon1, lat0, lat1] = meta.city;
  const gw = 900, gh = 700;
  const origin = ecef((lat0 + lat1) / 2, (lon0 + lon1) / 2, 0);
  const pos = new Float32Array(gw * gh * 3), uv = new Float32Array(gw * gh * 2);
  const sample = (u, v) => {
    const x = u * (w - 1), y = v * (h - 1);
    const x0 = Math.min(w - 2, Math.floor(x)), y0 = Math.min(h - 2, Math.floor(y)), fx = x - x0, fy = y - y0;
    const a = hm[y0 * w + x0], b = hm[y0 * w + x0 + 1], c = hm[(y0 + 1) * w + x0], d = hm[(y0 + 1) * w + x0 + 1];
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy;
  };
  for (let j = 0; j < gh; j++) for (let i = 0; i < gw; i++) {
    const u = i / (gw - 1), v = j / (gh - 1);
    const edge = i === 0 || j === 0 || i === gw - 1 || j === gh - 1;
    // the DEM softens the far peaks; lift them so the landing matches the footage
    const la = lerp(lat1, lat0, v), lo = lerp(lon0, lon1, u);
    const dd = Math.hypot((la - DRONE.lat) * 111.19, (lo - DRONE.lon) * 111.19 * Math.cos(DRONE.lat * D2R));
    const hk = edge ? -0.08 : sample(u, v) / 1000 * (1 + 0.17 * smooth(5.8, 8.0, dd));
    const p = ecef(la, lo, hk).sub(origin);
    pos.set([p.x, p.y, p.z], (j * gw + i) * 3);
    uv.set([u, 1 - v], (j * gw + i) * 2);
  }
  const idx = new Uint32Array((gw - 1) * (gh - 1) * 6);
  let k = 0;
  for (let j = 0; j < gh - 1; j++) for (let i = 0; i < gw - 1; i++) {
    const a = j * gw + i, b = a + 1, c = a + gw, d = c + 1;
    idx.set([a, c, b, b, c, d], k); k += 6;
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  g.setIndex(new THREE.BufferAttribute(idx, 1));
  g.computeVertexNormals();
  const mat = new THREE.ShaderMaterial({
    uniforms: {
      regTex: { value: tex.reg }, cityTex: { value: tex.city }, dayTex: { value: tex.day },
      regBox: { value: new THREE.Vector4(...meta.regional) }, cityBox: { value: new THREE.Vector4(...meta.city) },
      sunDir: { value: sunDir }, hazeAmt: { value: 0 }, visibility: { value: 80 }, hazeDay: { value: 1 },
      fade: { value: 1 },
    },
    transparent: false,
    vertexShader: /* glsl */`
      #include <common>
      #include <logdepthbuf_pars_vertex>
      varying vec2 vUv; varying vec3 vPos; varying vec3 vN;
      void main() {
        vUv = uv;
        vec4 wp = modelMatrix * vec4(position, 1.0);
        vPos = wp.xyz; vN = normalize(mat3(modelMatrix) * normal);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        #include <logdepthbuf_vertex>
      }`,
    fragmentShader: /* glsl */`
      #include <common>
      #include <logdepthbuf_pars_fragment>
      varying vec2 vUv; varying vec3 vPos; varying vec3 vN;
      ${SHARED_GLSL}
      void main() {
        #include <logdepthbuf_fragment>
        float lon = mix(cityBox.x, cityBox.y, vUv.x), lat = mix(cityBox.z, cityBox.w, vUv.y);
        vec3 base = vec3(.05, .19, .33);
        patchColor(lat, lon, base);
        vec3 up = normalize(vPos);
        float ndl = dot(normalize(vN), sunDir);
        float flat_ = dot(up, sunDir);
        float shade = clamp(.78 + .9 * (ndl - flat_), .35, 1.35);
        vec3 col = base * shade;
        col = haze(col, vPos, 1.);
        gl_FragColor = vec4(col, 1.);
      }`,
  });
  const m = new THREE.Mesh(g, mat);
  m.position.copy(origin);
  m.frustumCulled = false;
  scene.add(m);
  return m;
}

function makeAssets() {
  const r = rng(7);
  for (let k = 0; k < 6; k++) {
    const g = Object.assign(document.createElement('canvas'), { width: 384, height: 384 });
    const gc = g.getContext('2d'), img = gc.createImageData(384, 384);
    for (let i = 0; i < img.data.length; i += 4) { const v = r() * 255; img.data[i] = img.data[i + 1] = img.data[i + 2] = v; img.data[i + 3] = 255; }
    gc.putImageData(img, 0, 0);
    grain.push(g);
  }
  // soft cloud puffs for the punch through the cloud deck
  for (let k = 0; k < 5; k++) {
    const c = Object.assign(document.createElement('canvas'), { width: 512, height: 512 });
    const g = c.getContext('2d');
    for (let i = 0; i < 46; i++) {
      const a = r() * Math.PI * 2, d = Math.pow(r(), .7) * 170, rr = 50 + r() * 110;
      const x = 256 + Math.cos(a) * d, y = 256 + Math.sin(a) * d * .7;
      const gr = g.createRadialGradient(x, y, 0, x, y, rr);
      const sh = 225 + r() * 30;
      gr.addColorStop(0, `rgba(${sh},${sh + 3},${Math.min(255, sh + 10)},.22)`);
      gr.addColorStop(1, 'rgba(255,255,255,0)');
      g.fillStyle = gr; g.fillRect(0, 0, 512, 512);
    }
    puffs.push(c);
  }
}

async function init() {
  await Promise.all([document.fonts.load(`900 100px ${DISP}`), document.fonts.load(`800 100px ${DISP}`),
    document.fonts.load(`500 100px ${MONO}`), document.fonts.load(`700 100px ${MONO}`)]);
  meta = await (await fetch('data/meta.json')).json();
  videoTracks = await (await fetch('data/tracks.json')).json();
  const [day, night, bump, reg, cityT] = await Promise.all([
    loadTex('data/earth_day_4096.jpg'), loadTex('data/earth_night_4096.jpg'), loadTex('data/earth_bump_roughness_clouds_4096.jpg'),
    loadTex('data/s2_regional.png'), loadTex('data/s2_city.png'),
  ]);
  const tex = { day, night, bump, reg, city: cityT };
  globe = makeGlobe(tex);
  atmo = makeAtmosphere();
  stars = makeStars();
  city = await makeCity(tex);
  makeAssets();
  // warm up so the first timed frame doesn't pay for shader compiles
  renderer.compile(scene, camera);
  window.ready = true;
}

// ---------- 3D frame ----------
function render3D(t) {
  const s = camState(t);
  const { pos, alt } = applyCamera(camera, s);
  const gu = globe.material.uniforms, cu = city.material.uniforms;
  gu.cloudShift.value = t * 0.0012;
  gu.gridAmt.value = .55 * smooth(2.8, 4.6, t) * (1 - smooth(7.4, 8.6, t));
  gu.cloudAmt.value = 1;
  const low = alt < 160;
  city.visible = low;
  gu.holeAmt.value = low ? 1 : 0;
  // aerial perspective thickens as we sink into the atmosphere
  const hz = smooth(400, 20, alt);
  gu.hazeAmt.value = cu.hazeAmt.value = hz * .85;
  gu.visibility.value = cu.visibility.value = lerp(400, 38, smooth(300, 1, alt));
  stars.material.uniforms.amt.value = 1 - smooth(250, 60, alt);
  renderer.render(scene, camera);
  return { s, pos, alt };
}

// project a world point to screen pixels; null if behind the camera or the globe
function project(v, occlude = true) {
  const camP = camera.position;
  if (occlude) {
    // hidden behind the planet?
    const d = v.clone().sub(camP), L = d.length(); d.divideScalar(L);
    const b = camP.dot(d), c = camP.lengthSq() - (R - 2) * (R - 2), disc = b * b - c;
    if (disc > 0) { const t0 = -b - Math.sqrt(disc); if (t0 > 0 && t0 < L - 1) return null; }
  }
  const p = v.clone().project(camera);
  if (p.z > 1) return null;
  return { x: (p.x + 1) / 2 * W, y: (1 - p.y) / 2 * H };
}

// ---------- HUD ----------
function fmtAlt(a) {
  if (a >= 1000) return `${Math.round(a).toLocaleString('en-US')} KM`;
  if (a >= 10) return `${a.toFixed(1)} KM`;
  return `${Math.round(a * 1000).toLocaleString('en-US')} M`;
}
function fmtLat(v) { return `${Math.abs(v).toFixed(4)}° ${v < 0 ? 'S' : 'N'}`; }
function fmtLon(v) { return `${Math.abs(v).toFixed(4)}° ${v < 0 ? 'W' : 'E'}`; }

function typed(str, t, t0, cps = 38) { return str.slice(0, Math.max(0, Math.floor((t - t0) * cps))); }

function brackets(x, y, w, h, L, alpha) {
  ctx.globalAlpha = alpha;
  ctx.beginPath();
  for (const [cx, cy, sx, sy] of [[x, y, 1, 1], [x + w, y, -1, 1], [x, y + h, 1, -1], [x + w, y + h, -1, -1]]) {
    ctx.moveTo(cx, cy + sy * L); ctx.lineTo(cx, cy); ctx.lineTo(cx + sx * L, cy);
  }
  ctx.stroke();
  ctx.globalAlpha = 1;
}

const STATUS = [
  [0.6, 'ORBIT ESTABLISHED'], [3.2, 'SCANNING SURFACE'], [5.6, 'TARGET LOCKED — CAPE TOWN'], [7.0, 'DESCENT INITIATED'],
  [8.6, 'ENTERING ATMOSPHERE'], [10.8, 'FINAL APPROACH'], [12.7, 'WELCOME TO CAPE TOWN'],
];

function drawHUD(t, frame, st) {
  const a = smooth(.2, .9, t) * (1 - smooth(13.4, 14.2, t));
  if (a <= 0) return;
  ctx.save();
  ctx.globalAlpha = a;
  ctx.strokeStyle = 'rgba(255,255,255,.75)'; ctx.fillStyle = '#fff'; ctx.lineWidth = 2;
  const m = 52;
  brackets(m, m, W - 2 * m, H - 2 * m, 38, a);
  ctx.globalAlpha = a;
  ctx.font = `500 17px ${MONO}`; ctx.textAlign = 'left';
  ctx.fillText('ORBITAL DESCENT  //  ZA-CPT', m + 20, m + 38);
  ctx.textAlign = 'right';
  const tt = Math.min(t, 99);
  ctx.fillText(`T+${String(Math.floor(tt)).padStart(2, '0')}:${String(Math.floor((tt % 1) * 100)).padStart(2, '0')}  ·  F${String(frame).padStart(4, '0')}`, W - m - 20, m + 38);
  if (Math.floor(t * 2) % 2 === 0) { ctx.fillStyle = '#FF3B30'; ctx.beginPath(); ctx.arc(W - m - 295, m + 32, 6, 0, Math.PI * 2); ctx.fill(); ctx.fillStyle = '#fff'; }

  // altitude readout + log ladder
  const lx = m + 20, ly = 330;
  ctx.textAlign = 'left';
  ctx.font = `500 15px ${MONO}`; ctx.globalAlpha = a * .7; ctx.fillText('ALTITUDE', lx, ly - 18);
  ctx.globalAlpha = a; ctx.font = `700 34px ${MONO}`; ctx.fillText(fmtAlt(st.alt), lx, ly + 20);
  const la = Math.log10(Math.max(st.alt, .1));
  ctx.save(); ctx.beginPath(); ctx.rect(lx, ly + 50, 260, 380); ctx.clip();
  ctx.font = `500 13px ${MONO}`; ctx.lineWidth = 1.5;
  for (let e = -1; e <= 5; e += .25) {
    const y = ly + 240 + (la - e) * 150;
    const major = Math.abs(e - Math.round(e)) < .01;
    ctx.globalAlpha = a * (major ? .9 : .4);
    ctx.beginPath(); ctx.moveTo(lx, y); ctx.lineTo(lx + (major ? 30 : 14), y); ctx.stroke();
    if (major) ctx.fillText(fmtAlt(Math.pow(10, e)), lx + 40, y + 5);
  }
  ctx.restore();
  ctx.globalAlpha = a; ctx.fillStyle = C.amber;
  ctx.beginPath(); ctx.moveTo(lx + 236, ly + 240); ctx.lineTo(lx + 252, ly + 232); ctx.lineTo(lx + 252, ly + 248); ctx.fill();
  ctx.fillRect(lx, ly + 239, 230, 2);
  ctx.fillStyle = '#fff';

  // right column: velocity / sun / heading
  const v = Math.abs(Math.log(camState(t + 1 / FPS).range) - Math.log(camState(t).range)) * FPS * st.alt;
  const rx = W - m - 20;
  ctx.textAlign = 'right';
  const rows = [['DESCENT RATE', `${(v).toFixed(v > 100 ? 0 : 2)} KM/S`], ['HEADING', `${st.s.heading.toFixed(1).padStart(5, '0')}°`],
    ['TILT', `${st.s.tilt.toFixed(1)}°`], ['FOV', `${st.s.vfov.toFixed(1)}°`]];
  rows.forEach(([k, val], i) => {
    ctx.globalAlpha = a * .7; ctx.font = `500 15px ${MONO}`; ctx.fillText(k, rx, 330 + i * 78 - 18);
    ctx.globalAlpha = a; ctx.font = `700 26px ${MONO}`; ctx.fillText(val, rx, 330 + i * 78 + 14);
  });

  // nadir coordinates
  const nadir = toLatLon(camera.position);
  ctx.textAlign = 'left'; ctx.font = `500 17px ${MONO}`;
  ctx.fillText(`NADIR  ${fmtLat(nadir.lat)}  ${fmtLon(nadir.lon)}`, m + 20, H - m - 26);

  // heading tape
  const hx = W / 2, hy = m + 30;
  ctx.save(); ctx.beginPath(); ctx.rect(hx - 300, hy - 25, 600, 50); ctx.clip();
  ctx.textAlign = 'center'; ctx.font = `500 14px ${MONO}`;
  for (let d = -360; d <= 720; d += 15) {
    const x = hx + (d - st.s.heading) * 4;
    if (x < hx - 320 || x > hx + 320) continue;
    const major = d % 45 === 0;
    ctx.globalAlpha = a * (1 - Math.abs(x - hx) / 320) * (major ? 1 : .5);
    ctx.fillRect(x - 1, hy + 2, 2, major ? 12 : 6);
    if (major) ctx.fillText(['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'][((d / 45) % 8 + 8) % 8], x, hy - 6);
  }
  ctx.restore();
  ctx.globalAlpha = a; ctx.fillStyle = C.amber;
  ctx.beginPath(); ctx.moveTo(hx, hy + 18); ctx.lineTo(hx - 7, hy + 28); ctx.lineTo(hx + 7, hy + 28); ctx.fill();
  ctx.fillStyle = '#fff';

  // status pill
  let cur = null;
  for (const s of STATUS) if (t >= s[0]) cur = s;
  if (cur) {
    const txt = typed(cur[1], t, cur[0]);
    ctx.font = `700 18px ${MONO}`; ctx.textAlign = 'center';
    const wpx = ctx.measureText(cur[1]).width + 60;
    ctx.globalAlpha = a * .9;
    ctx.fillStyle = 'rgba(0,0,0,.35)'; ctx.fillRect(W / 2 - wpx / 2, H - m - 58, wpx, 44);
    ctx.strokeStyle = cur[1].startsWith('TARGET') || cur[1].startsWith('WELCOME') ? C.amber : 'rgba(255,255,255,.6)';
    ctx.strokeRect(W / 2 - wpx / 2, H - m - 58, wpx, 44);
    ctx.fillStyle = '#fff'; ctx.globalAlpha = a;
    ctx.fillText(txt + (Math.floor(t * 5) % 2 ? '▌' : ' '), W / 2, H - m - 30);
  }
  ctx.restore();
}

function drawReticle(t, st) {
  const vis = smooth(4.4, 5.0, t) * (1 - smooth(10.2, 11.0, t));
  if (vis <= 0) return;
  const p = project(ecef(CPT.lat, CPT.lon, 0));
  if (!p) return;
  const lock = E.outExpo(prog(t, 4.6, 5.7));
  ctx.save();
  ctx.globalAlpha = vis;
  ctx.strokeStyle = C.amber; ctx.fillStyle = C.amber; ctx.lineWidth = 2;
  // converging brackets
  const s = lerp(420, 46, lock);
  ctx.save(); ctx.translate(p.x, p.y); ctx.rotate((1 - lock) * Math.PI / 2);
  brackets(-s, -s, 2 * s, 2 * s, 18, vis);
  ctx.restore();
  ctx.globalAlpha = vis;
  // rotating dashed ring
  ctx.setLineDash([6, 10]); ctx.lineDashOffset = -t * 60;
  ctx.beginPath(); ctx.arc(p.x, p.y, s * 1.35, 0, Math.PI * 2); ctx.stroke();
  ctx.setLineDash([]);
  // pulse rings once locked
  for (let k = 0; k < 3; k++) {
    const ph = ((t - 5.7) * 1.2 + k / 3) % 1;
    if (t < 5.7) break;
    ctx.globalAlpha = vis * (1 - ph) * .9;
    ctx.beginPath(); ctx.arc(p.x, p.y, 8 + ph * 90, 0, Math.PI * 2); ctx.stroke();
  }
  ctx.globalAlpha = vis;
  ctx.beginPath(); ctx.arc(p.x, p.y, 5, 0, Math.PI * 2); ctx.fill();
  // crosshair ticks
  for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
    ctx.beginPath(); ctx.moveTo(p.x + dx * (s + 8), p.y + dy * (s + 8)); ctx.lineTo(p.x + dx * (s + 26), p.y + dy * (s + 26)); ctx.stroke();
  }
  // label
  const lp = E.outExpo(prog(t, 5.5, 6.1));
  if (lp > 0) {
    const x1 = p.x + 60, y1 = p.y - 60, x2 = x1 + 70 * lp;
    ctx.beginPath(); ctx.moveTo(p.x + s * .7, p.y - s * .7); ctx.lineTo(x1, y1); ctx.lineTo(x2, y1); ctx.stroke();
    ctx.globalAlpha = vis * lp;
    ctx.fillStyle = '#fff'; ctx.textAlign = 'left';
    ctx.font = `800 34px ${DISP}`; ctx.fillText(typed('CAPE TOWN', t, 5.6, 30), x2 + 14, y1 + 10);
    ctx.font = `500 15px ${MONO}`; ctx.fillStyle = C.amber;
    ctx.fillText(typed(`${fmtLat(CPT.lat)}  ${fmtLon(CPT.lon)}  ·  ZA`, t, 5.8, 50), x2 + 15, y1 + 34);
  }
  ctx.restore();
}

function drawScan(t) {
  const sp = prog(t, 3.3, 4.9);
  if (sp <= 0 || sp >= 1) return;
  const y = lerp(150, H - 150, E.inOutSine(sp));
  const g = ctx.createLinearGradient(0, y - 120, 0, y);
  g.addColorStop(0, 'rgba(127,231,255,0)'); g.addColorStop(1, 'rgba(127,231,255,.16)');
  ctx.fillStyle = g; ctx.fillRect(0, y - 120, W, 120);
  ctx.fillStyle = 'rgba(127,231,255,.85)'; ctx.fillRect(0, y, W, 2);
}

function drawFlare(t) {
  const camP = camera.position, c = camP.clone().multiplyScalar(-1).normalize();
  const rho = Math.asin(Math.min(1, R * 1.012 / camP.length()));
  const beta = Math.acos(clamp(c.dot(sunDir), -1, 1));
  const vis = smooth(rho - 0.002, rho + 0.03, beta);
  if (vis <= 0.001) return;
  const sp = camP.clone().add(sunDir.clone().multiplyScalar(1e6)).project(camera);
  if (sp.z > 1) return;
  const x = (sp.x + 1) / 2 * W, y = (1 - sp.y) / 2 * H;
  const burst = Math.exp(-Math.pow((beta - rho - .012) / .02, 2));
  const fade = 1 - smooth(5.0, 7.0, t);
  const I = vis * fade + burst * 0.8 * fade;
  if (I <= 0.002) return;
  ctx.save();
  ctx.globalCompositeOperation = 'lighter';
  const glow = (r, a, col) => {
    const g = ctx.createRadialGradient(x, y, 0, x, y, r);
    g.addColorStop(0, `rgba(${col},${a})`); g.addColorStop(1, `rgba(${col},0)`);
    ctx.fillStyle = g; ctx.fillRect(x - r, y - r, 2 * r, 2 * r);
  };
  glow(900 * (0.6 + burst * .6), .55 * I, '255,190,120');
  glow(260, .9 * I, '255,240,220');
  glow(60, 1 * I, '255,255,255');
  // anamorphic streak
  ctx.save(); ctx.translate(x, y); ctx.scale(1, .02);
  const gs = ctx.createRadialGradient(0, 0, 0, 0, 0, 1500);
  gs.addColorStop(0, `rgba(170,210,255,${.9 * I})`); gs.addColorStop(1, 'rgba(170,210,255,0)');
  ctx.fillStyle = gs; ctx.fillRect(-1500, -1500, 3000, 3000);
  ctx.restore();
  // starburst rays
  ctx.save(); ctx.translate(x, y);
  for (let k = 0; k < 12; k++) {
    ctx.rotate(Math.PI / 6 + .03);
    const L = (200 + (k % 3) * 160) * (0.5 + burst);
    const g = ctx.createLinearGradient(0, 0, L, 0);
    g.addColorStop(0, `rgba(255,235,210,${.35 * I})`); g.addColorStop(1, 'rgba(255,235,210,0)');
    ctx.fillStyle = g; ctx.fillRect(0, -1.5, L, 3);
  }
  ctx.restore();
  // ghosts along the axis through the frame centre
  const ghosts = [[.4, 40, '120,255,200', .12], [.7, 90, '255,150,90', .08], [1.25, 26, '150,180,255', .18], [1.6, 140, '255,210,140', .06], [1.9, 60, '170,120,255', .1]];
  for (const [k, r, col, a] of ghosts) {
    const gx = x + (W / 2 - x) * k, gy = y + (H / 2 - y) * k;
    const g = ctx.createRadialGradient(gx, gy, r * .2, gx, gy, r);
    g.addColorStop(0, `rgba(${col},${a * I})`); g.addColorStop(.8, `rgba(${col},${a * .7 * I})`); g.addColorStop(1, `rgba(${col},0)`);
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(gx, gy, r, 0, Math.PI * 2); ctx.fill();
  }
  ctx.restore();
}

function drawClouds(t) {
  // passing through the cloud deck on the way down
  const a0 = 8.7, a1 = 10.6;
  if (t < a0 || t > a1) return;
  const r = rng(99);
  ctx.save();
  for (let i = 0; i < 46; i++) {
    const born = a0 + r() * (a1 - a0 - .55), life = .5 + r() * .35;
    const px = (r() - .5) * 2.4, py = (r() - .5) * 1.6, sz = .5 + r() * .9, img = puffs[i % puffs.length], rot = r() * 6;
    const u = (t - born) / life;
    if (u < 0 || u > 1) continue;
    const z = lerp(1, .08, E.inCubic(u));
    const x = W / 2 + px * W * .25 / z, y = H / 2 + py * H * .25 / z;
    const s = sz * 520 / z;
    ctx.globalAlpha = Math.sin(Math.PI * u) * .75;
    ctx.save(); ctx.translate(x, y); ctx.rotate(rot); ctx.drawImage(img, -s / 2, -s / 2, s, s); ctx.restore();
  }
  // a brief whiteout at the densest part
  const wo = Math.exp(-Math.pow((t - 9.65) / .22, 2)) * .4;
  ctx.globalAlpha = wo; ctx.fillStyle = '#EEF4FA'; ctx.fillRect(0, 0, W, H);
  ctx.restore();
}

// ---------- video section ----------
const LANDMARKS = [
  { key: 'table', name: 'TABLE MOUNTAIN', sub: '1,085 M  ·  NEW 7 WONDERS OF NATURE', t0: 14.1, dx: 0, dy: -150, side: 1 },
  { key: 'lion', name: "LION'S HEAD", sub: '669 M', t0: 14.45, dx: 86, dy: -116, side: -1 },
  { key: 'devil', name: "DEVIL'S PEAK", sub: '1,000 M', t0: 14.75, dx: -40, dy: -130, side: 1 },
  { key: 'signal', name: 'SIGNAL HILL', sub: '350 M', t0: 15.05, dx: 70, dy: -110, side: 1 },
  { key: 'stadium', name: 'CAPE TOWN STADIUM', sub: 'GREEN POINT', t0: 15.35, dx: -60, dy: -170, side: 1 },
  { key: 'waterfront', name: 'V&A WATERFRONT', sub: 'TABLE BAY HARBOUR', t0: 15.65, dx: 90, dy: -120, side: 1 },
];
const LM_OUT = 18.6;

const vimg = new Image();
let vloaded = -1;
async function loadVideoFrame(i) {
  if (vloaded === i) return;
  vimg.src = `data/video/v_${String(i + 1).padStart(4, '0')}.jpg`;
  await vimg.decode();
  vloaded = i;
}
const skyC = Object.assign(document.createElement('canvas'), { width: W, height: 420 });
const sctx = skyC.getContext('2d', { willReadFrequently: true });
const txtC = Object.assign(document.createElement('canvas'), { width: W, height: 420 });
const tctx = txtC.getContext('2d');

function drawLandmark(lm, t, p, i) {
  const out = E.outCubic(prog(t, LM_OUT + i * .08, LM_OUT + .35 + i * .08));
  if (t < lm.t0) return;
  const pin = E.outBack(prog(t, lm.t0, lm.t0 + .35)) * (1 - out);
  if (pin <= 0) return;
  const line = E.outExpo(prog(t, lm.t0 + .1, lm.t0 + .55)) * (1 - out);
  const txt = E.outExpo(prog(t, lm.t0 + .3, lm.t0 + .8));
  ctx.save();
  // anchor
  ctx.fillStyle = '#fff';
  ctx.beginPath(); ctx.arc(p.x, p.y, Math.max(0, 6 * pin), 0, Math.PI * 2); ctx.fill();
  const ph = ((t - lm.t0) * .9) % 1;
  ctx.strokeStyle = `rgba(255,255,255,${(1 - ph) * .8 * (1 - out)})`; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.arc(p.x, p.y, 8 + ph * 34, 0, Math.PI * 2); ctx.stroke();
  // leader
  const ex = p.x + lm.dx, ey = p.y + lm.dy;
  ctx.strokeStyle = 'rgba(255,255,255,.9)'; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(p.x, p.y - 10);
  ctx.lineTo(lerp(p.x, ex, line), lerp(p.y - 10, ey, line)); ctx.stroke();
  if (line > .98) {
    const w = 40 * txt;
    ctx.beginPath(); ctx.moveTo(ex, ey); ctx.lineTo(ex + w * lm.side, ey); ctx.stroke();
  }
  // label, revealed through a mask
  if (txt > 0) {
    ctx.font = `800 30px ${DISP}`;
    const tw = Math.max(ctx.measureText(lm.name).width, 10);
    ctx.font = `500 15px ${MONO}`;
    const sw = ctx.measureText(lm.sub).width;
    const bw = Math.max(tw, sw) + 36;
    const bx = lm.side > 0 ? ex + 40 : ex - 40 - bw, by = ey - 34;
    ctx.save();
    ctx.beginPath(); ctx.rect(lm.side > 0 ? bx : bx + bw * (1 - txt * (1 - out)), by - 4, bw * txt * (1 - out), 82); ctx.clip();
    ctx.fillStyle = 'rgba(8,14,24,.55)'; ctx.fillRect(bx, by, bw, 74);
    ctx.fillStyle = C.amber; ctx.fillRect(lm.side > 0 ? bx : bx + bw - 4, by, 4, 74);
    ctx.fillStyle = '#fff'; ctx.textAlign = 'left';
    ctx.font = `800 30px ${DISP}`; ctx.fillText(lm.name, bx + 18, by + 36);
    ctx.font = `500 15px ${MONO}`; ctx.fillStyle = 'rgba(255,255,255,.75)'; ctx.fillText(lm.sub, bx + 18, by + 60);
    ctx.restore();
  }
  ctx.restore();
}

// "CAPE TOWN" set into the sky, tucked behind Table Mountain
function drawSkyTitle(t, vi) {
  const a = smooth(18.9, 19.3, t);
  if (a <= 0) return;
  const size = 230, base = 318;
  tctx.clearRect(0, 0, W, 420);
  tctx.save();
  tctx.font = `900 ${size}px ${DISP}`; tctx.textAlign = 'center'; tctx.fillStyle = '#fff';
  const word = 'CAPE TOWN', chars = [...word];
  const track = lerp(60, 14, E.outExpo(prog(t, 18.9, 20.4))) + (t - 18.9) * 4;
  const ws = chars.map(c => tctx.measureText(c).width);
  const total = ws.reduce((x, y) => x + y, 0) + track * (chars.length - 1);
  let x = W / 2 - total / 2;
  chars.forEach((ch, i) => {
    const p = E.outExpo(prog(t, 18.95 + i * .055, 19.75 + i * .055));
    tctx.globalAlpha = p;
    tctx.fillText(ch, x + ws[i] / 2, base + (1 - p) * 140);
    x += ws[i] + track;
  });
  tctx.restore();
  // keep the text only where the frame is sky
  const img = sctx.getImageData(0, 0, W, 420), d = img.data;
  for (let i = 0; i < d.length; i += 4) {
    const r = d[i], g = d[i + 1], b = d[i + 2];
    const sky = clamp((b - r - 55) / 30) * clamp((b - 120) / 40);
    d[i] = d[i + 1] = d[i + 2] = 255; d[i + 3] = sky * 255;
  }
  sctx.putImageData(img, 0, 0);
  tctx.save(); tctx.globalCompositeOperation = 'destination-in';
  tctx.filter = 'blur(1.2px)'; tctx.drawImage(skyC, 0, 0); tctx.restore();
  ctx.save();
  ctx.globalAlpha = a * (1 - smooth(23.3, 23.9, t));
  ctx.shadowColor = 'rgba(0,30,80,.25)'; ctx.shadowBlur = 30;
  ctx.drawImage(txtC, 0, 0);
  ctx.restore();
  // subtitle under the skyline line
  const sp = E.outExpo(prog(t, 19.9, 20.7)) * (1 - smooth(23.3, 23.9, t));
  if (sp > 0) {
    ctx.save();
    ctx.globalAlpha = sp; ctx.fillStyle = '#fff'; ctx.textAlign = 'center';
    ctx.shadowColor = 'rgba(0,0,0,.5)'; ctx.shadowBlur = 16;
    ctx.font = `700 22px ${MONO}`;
    const sub = 'SOUTH AFRICA   ·   THE MOTHER CITY';
    ctx.letterSpacing = `${lerp(18, 8, sp)}px`;
    ctx.fillText(sub, W / 2, 1000);
    ctx.font = `500 16px ${MONO}`; ctx.letterSpacing = '4px'; ctx.globalAlpha = sp * .8;
    ctx.fillText(`${fmtLat(CPT.lat)}   ${fmtLon(CPT.lon)}`, W / 2, 1032);
    ctx.restore();
  }
}

async function drawVideo(t) {
  const vt = Math.max(0, t - T_VIDEO);
  const vi = Math.min(VIDEO_FRAMES - 1, Math.floor(vt * VIDEO_FPS));
  await loadVideoFrame(vi);
  const mix = E.inOutSine(prog(t, T_VIDEO, T_VIDEO + .8));
  ctx.save();
  ctx.globalAlpha = mix;
  ctx.drawImage(vimg, 0, 0, W, H);
  ctx.restore();
  if (t >= 18.9) { sctx.clearRect(0, 0, W, 420); sctx.drawImage(vimg, 0, 0, W, 420, 0, 0, W, 420); }
  // a soft bloom to bridge the dissolve
  const bl = Math.exp(-Math.pow((t - (T_VIDEO + .3)) / .35, 2)) * .32;
  if (bl > .01) { ctx.fillStyle = `rgba(235,244,255,${bl})`; ctx.fillRect(0, 0, W, H); }
  if (mix < 1) return;
  // gentle grade: lift the bottom, darken the top edge for type
  const g = ctx.createLinearGradient(0, H * .62, 0, H);
  g.addColorStop(0, 'rgba(0,10,25,0)'); g.addColorStop(1, `rgba(0,10,25,${.55 * smooth(19.6, 20.4, t)})`);
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  LANDMARKS.forEach((lm, i) => {
    const tr = videoTracks[lm.key];
    if (tr) drawLandmark(lm, t, { x: tr[vi][0], y: tr[vi][1] }, i);
  });
  drawSkyTitle(t, vi);
  // minimal frame for the footage
  const fa = smooth(13.8, 14.4, t) * (1 - smooth(23.3, 23.9, t));
  ctx.save(); ctx.globalAlpha = fa * .8; ctx.strokeStyle = '#fff'; ctx.lineWidth = 2;
  brackets(52, 52, W - 104, H - 104, 38, fa * .8);
  ctx.globalAlpha = fa; ctx.fillStyle = '#fff'; ctx.font = `500 17px ${MONO}`; ctx.textAlign = 'left';
  ctx.fillText('CAPE TOWN  //  GREEN POINT', 72, 90);
  ctx.textAlign = 'right';
  ctx.fillText(`ALT ${Math.round(540 + vt * 3)} M  ·  HDG ${DRONE.heading.toFixed(1)}°`, W - 72, 90);
  ctx.restore();
}

function finish(t, frame) {
  // vignette
  const v = ctx.createRadialGradient(W / 2, H / 2, H * .5, W / 2, H / 2, H * 1.05);
  v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,.35)');
  ctx.fillStyle = v; ctx.fillRect(0, 0, W, H);
  // film grain
  ctx.save(); ctx.globalAlpha = .06; ctx.globalCompositeOperation = 'overlay';
  const g = grain[frame % grain.length], ox = (frame * 131) % 384, oy = (frame * 71) % 384;
  for (let x = -ox; x < W; x += 384) for (let y = -oy; y < H; y += 384) ctx.drawImage(g, x, y);
  ctx.restore();
  // fade in from black / out to black
  const fb = Math.max(1 - smooth(0, .9, t), smooth(DUR - .7, DUR - .05, t));
  if (fb > 0) { ctx.fillStyle = `rgba(0,0,0,${fb})`; ctx.fillRect(0, 0, W, H); }
}

window.renderFrame = async function (frame) {
  const t = frame / FPS;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, W, H);
  ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
  const videoOnly = t >= T_VIDEO + .85;
  let st = null;
  if (videoOnly) {
    const s = camState(T_VIDEO + .85);
    st = { s, ...applyCamera(camera, s) };
  } else {
    st = render3D(t);
    drawFlare(t);
    drawScan(t);
    drawClouds(t);
    drawReticle(t, st);
  }
  if (t >= T_VIDEO) await drawVideo(t);
  if (st) drawHUD(t, frame, st);
  finish(t, frame);
};

init().catch(e => { console.error(e); window.initError = String(e); });
