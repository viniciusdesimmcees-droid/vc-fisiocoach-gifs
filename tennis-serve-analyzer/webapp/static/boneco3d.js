// Boneco 3D VF — construtor compartilhado (usado pelo boneco, comparativo e saque 3D).
// Requer THREE global (three.min.js local).
(function (global) {
  const REG = {
    cabeca: [[0, 1.62, 0.10]],
    trapezio: [[0.12, 1.46, -0.05], [-0.12, 1.46, -0.05]],
    ombros: [[0.26, 1.38, 0.02], [-0.26, 1.38, 0.02]],
    ombro_dir: [[-0.26, 1.38, 0.02]], ombro_esq: [[0.26, 1.38, 0.02]],
    peito: [[0, 1.27, 0.15]],
    costas: [[0, 1.24, -0.15]],
    abdomen: [[0, 1.04, 0.14]],
    lombar: [[0, 1.00, -0.14]],
    tronco: [[0, 1.15, 0.16]],
    braco_dir: [[-0.33, 1.14, 0.04]], braco_esq: [[0.33, 1.14, 0.04]],
    antebraco_dir: [[-0.40, 0.90, 0.06]], antebraco_esq: [[0.40, 0.90, 0.06]],
    pelvis: [[0, 0.94, 0.13]],
    gluteos: [[0.10, 0.90, -0.13], [-0.10, 0.90, -0.13]],
    coxas: [[0.12, 0.64, 0.11], [-0.12, 0.64, 0.11]],
    joelhos: [[0.12, 0.46, 0.09], [-0.12, 0.46, 0.09]],
    panturrilhas: [[0.12, 0.26, -0.09], [-0.12, 0.26, -0.09]],
  };

  function bodyMaterial() {
    return new THREE.MeshStandardMaterial({ color: 0xdfe8e2, roughness: 0.55, metalness: 0.05 });
  }

  // boneco ESTÁTICO (postura anatômica) com base
  function buildMannequin(group, opts) {
    const mat = (opts && opts.material) || bodyMaterial();
    const V = (a) => new THREE.Vector3(a[0], a[1], a[2]);
    function limb(a, b, r) {
      a = V(a); b = V(b);
      const d = new THREE.Vector3().subVectors(b, a), len = d.length();
      const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r * 0.85, len, 16), mat);
      m.position.copy(a).addScaledVector(d, 0.5);
      m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.clone().normalize());
      group.add(m); return m;
    }
    function ball(p, r, sy, sz) {
      const m = new THREE.Mesh(new THREE.SphereGeometry(r, 22, 18), mat);
      m.position.copy(V(p)); m.scale.set(1, sy || 1, sz || 1); group.add(m); return m;
    }
    ball([0, 1.62, 0], 0.115, 1.08, 0.95);
    limb([0, 1.46, 0], [0, 1.54, 0], 0.05);
    const torso = new THREE.Mesh(new THREE.CylinderGeometry(0.17, 0.135, 0.50, 20), mat);
    torso.position.set(0, 1.22, 0); torso.scale.z = 0.72; group.add(torso);
    ball([0, 0.94, 0], 0.15, 0.72, 0.72);
    [1, -1].forEach((s) => {
      ball([s * 0.23, 1.39, 0], 0.062);
      limb([s * 0.23, 1.39, 0], [s * 0.32, 1.10, 0.02], 0.052);
      ball([s * 0.32, 1.10, 0.02], 0.052);
      limb([s * 0.32, 1.10, 0.02], [s * 0.39, 0.85, 0.06], 0.045);
      ball([s * 0.40, 0.82, 0.07], 0.052);
      limb([s * 0.11, 0.92, 0], [s * 0.12, 0.50, 0.02], 0.075);
      ball([s * 0.12, 0.49, 0.02], 0.062);
      limb([s * 0.12, 0.49, 0.02], [s * 0.13, 0.10, 0], 0.055);
      const foot = new THREE.Mesh(new THREE.BoxGeometry(0.10, 0.06, 0.20), mat);
      foot.position.set(s * 0.13, 0.045, 0.05); group.add(foot);
    });
    if (!opts || opts.ground !== false) {
      const ground = new THREE.Mesh(new THREE.CircleGeometry(0.75, 40),
        new THREE.MeshBasicMaterial({ color: 0x1a5c33, transparent: true, opacity: 0.25 }));
      ground.rotation.x = -Math.PI / 2; ground.position.y = 0.005; group.add(ground);
    }
  }

  // marcadores pulsantes; retorna lista de meshes (userData.idx aponta p/ ponto)
  function addMarkers(group, pontos) {
    const markers = [], regCount = {};
    pontos.forEach((p, idx) => {
      const positions = REG[p.regiao]; if (!positions) return;
      const n = regCount[p.regiao] = (regCount[p.regiao] || 0) + 1;
      positions.forEach((pos) => {
        const m = new THREE.Mesh(new THREE.SphereGeometry(0.048, 18, 14),
          new THREE.MeshBasicMaterial({ color: p.cor }));
        m.position.set(pos[0], pos[1] + (n - 1) * 0.075, pos[2]);
        m.userData = { idx, phase: Math.random() * 6 };
        const halo = new THREE.Mesh(new THREE.SphereGeometry(0.075, 18, 14),
          new THREE.MeshBasicMaterial({ color: p.cor, transparent: true, opacity: 0.28 }));
        m.add(halo);
        group.add(m); markers.push(m);
      });
    });
    return markers;
  }

  function pulse(markers, t, selectedIdx) {
    markers.forEach((m) => {
      const base = (m.userData.idx === selectedIdx) ? 1.45 : 1;
      m.scale.setScalar(base + 0.16 * Math.sin(t * 4 + m.userData.phase));
    });
  }

  // boneco ARTICULADO (para animação do saque). Retorna o rig com juntas.
  // Convenção: atleta olha para +z (câmera lateral em +x vê o plano sagital).
  function buildRig(group, opts) {
    const mat = (opts && opts.material) || bodyMaterial();
    function seg(len, r0, r1) { // cilindro apontando para -y a partir da origem
      const m = new THREE.Mesh(new THREE.CylinderGeometry(r0, r1, len, 16), mat);
      m.position.y = -len / 2; return m;
    }
    function joint(r) { return new THREE.Mesh(new THREE.SphereGeometry(r, 18, 14), mat); }

    const rig = { root: new THREE.Group() };
    group.add(rig.root);

    // pélvis (raiz do corpo)
    rig.pelvis = new THREE.Group(); rig.pelvis.position.set(0, 0.94, 0);
    rig.root.add(rig.pelvis);
    const hipMesh = joint(0.15); hipMesh.scale.set(1, 0.72, 0.72); rig.pelvis.add(hipMesh);

    // tronco + cabeça (giram juntos na inclinação)
    rig.torso = new THREE.Group(); rig.pelvis.add(rig.torso);
    const torsoMesh = new THREE.Mesh(new THREE.CylinderGeometry(0.17, 0.135, 0.50, 20), mat);
    torsoMesh.position.y = 0.28; torsoMesh.scale.z = 0.72; rig.torso.add(torsoMesh);
    const neck = seg(0.10, 0.05, 0.05); neck.position.y = 0.58; rig.torso.add(neck);
    const head = joint(0.115); head.position.y = 0.68; head.scale.set(1, 1.08, 0.95);
    rig.torso.add(head);

    // braços: ombro -> cotovelo -> punho (+ raquete no braço dominante)
    rig.arms = {};
    [['esq', 0.23], ['dir', -0.23]].forEach(([lado, x]) => {
      const sh = new THREE.Group(); sh.position.set(x, 0.45, 0); rig.torso.add(sh);
      sh.add(joint(0.062));
      sh.add(seg(0.30, 0.052, 0.048));
      const el = new THREE.Group(); el.position.y = -0.30; sh.add(el);
      el.add(joint(0.052));
      el.add(seg(0.26, 0.045, 0.042));
      const hand = joint(0.052); hand.position.y = -0.28; el.add(hand);
      rig.arms[lado] = { shoulder: sh, elbow: el, hand };
    });

    // pernas: quadril -> joelho -> tornozelo
    rig.legs = {};
    [['esq', 0.11], ['dir', -0.11]].forEach(([lado, x]) => {
      const hip = new THREE.Group(); hip.position.set(x, -0.02, 0); rig.pelvis.add(hip);
      hip.add(seg(0.42, 0.075, 0.062));
      const knee = new THREE.Group(); knee.position.y = -0.42; hip.add(knee);
      knee.add(joint(0.062));
      knee.add(seg(0.40, 0.055, 0.05));
      const foot = new THREE.Mesh(new THREE.BoxGeometry(0.10, 0.06, 0.20), mat);
      foot.position.set(0, -0.40, 0.05); knee.add(foot);
      rig.legs[lado] = { hip, knee, foot };
    });

    // raquete simples no braço indicado
    const domLado = (opts && opts.dom) || 'dir';
    const rmat = new THREE.MeshStandardMaterial({ color: 0x2f6b4a, roughness: 0.5 });
    const racket = new THREE.Group();
    const shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.015, 0.015, 0.30, 10), rmat);
    shaft.position.y = -0.15; racket.add(shaft);
    const headR = new THREE.Mesh(new THREE.TorusGeometry(0.10, 0.014, 10, 24), rmat);
    headR.position.y = -0.38; racket.add(headR);
    racket.position.y = -0.30;
    rig.arms[domLado].elbow.add(racket);
    rig.racket = racket;

    if (!opts || opts.ground !== false) {
      const ground = new THREE.Mesh(new THREE.CircleGeometry(0.85, 40),
        new THREE.MeshBasicMaterial({ color: 0x1a5c33, transparent: true, opacity: 0.25 }));
      ground.rotation.x = -Math.PI / 2; ground.position.y = 0.005; group.add(ground);
    }
    return rig;
  }

  global.VFBoneco = { REG, buildMannequin, addMarkers, pulse, buildRig, bodyMaterial };
})(window);
