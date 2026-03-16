// ── i18n ──────────────────────────────────────────────────────────────────
const I18N = {
  ja: {
    ally_team:'味方チーム', enemy_team:'敵チーム',
    chart_kda_breakdown:'KDA 内訳', chart_kda_ratio:'KDA 比率',
    chart_dmg:'ダメージ', chart_gold:'ゴールド', chart_cs:'CS',
    chart_vision:'視界スコア', chart_cc:'CC タイム（秒）',
    chart_scatter:'与ダメ / 被ダメ 分布',
    chart_radar_ally:'味方チーム — パフォーマンス',
    chart_radar_enemy:'敵チーム — パフォーマンス',
    chart_kp:'キルへの関与率（KP%）',
    chart_dead:'デス時間（試合時間比% ／ 低いほど良）',
    chart_gold_diff:'チームゴールドリード 推移',
    q_tank:'タンク', q_fighter:'ファイター', q_support:'サポート', q_carry:'キャリー',
    axis_dmg_dealt:'与ダメージ →', axis_dmg_taken:'← 被ダメージ',
    ally_lead:'▲ 味方リード', enemy_lead:'▼ 敵リード',
    legend_deaths:'Deaths ←', legend_kills:'→ K', legend_assists:'A',
    timeline_title:'時系列イベント（キル / オブジェクト）',
    search_ph:'検索: 例) キル / ドラゴン / ワード / ルル など',
    team_all:'Team: 全部', team_ally:'味方', team_enemy:'敵',
    type_all:'Type: 全部',
    pill_count:'イベント件数',
  },
  en: {
    ally_team:'Ally Team', enemy_team:'Enemy Team',
    chart_kda_breakdown:'KDA Breakdown', chart_kda_ratio:'KDA Ratio',
    chart_dmg:'Damage', chart_gold:'Gold', chart_cs:'CS',
    chart_vision:'Vision Score', chart_cc:'CC Time (sec)',
    chart_scatter:'Damage Dealt vs Taken',
    chart_radar_ally:'Ally Team — Performance',
    chart_radar_enemy:'Enemy Team — Performance',
    chart_kp:'Kill Participation (KP%)',
    chart_dead:'Dead Time (% of game, lower is better)',
    chart_gold_diff:'Team Gold Lead Over Time',
    q_tank:'Tank', q_fighter:'Fighter', q_support:'Support', q_carry:'Carry',
    axis_dmg_dealt:'Damage Dealt →', axis_dmg_taken:'← Damage Taken',
    ally_lead:'▲ Ally Lead', enemy_lead:'▼ Enemy Lead',
    legend_deaths:'Deaths ←', legend_kills:'→ K', legend_assists:'A',
    timeline_title:'Event Timeline (Kills / Objectives)',
    search_ph:'Search: e.g. kill / dragon / ward / champion name',
    team_all:'Team: All', team_ally:'Ally', team_enemy:'Enemy',
    type_all:'Type: All',
    pill_count:'Events',
  },
};
let currentLang = 'ja';
function t(key) { return (I18N[currentLang] || I18N.ja)[key] || key; }

function applyLang(lang) {
  currentLang = lang;
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    el.textContent = t(key);
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    el.placeholder = t(el.getAttribute('data-i18n-placeholder'));
  });
  document.querySelectorAll('[data-champ-en]').forEach(el => {
    if (lang === 'en') {
      if (!el.getAttribute('data-champ-ja')) el.setAttribute('data-champ-ja', el.textContent);
      el.textContent = el.getAttribute('data-champ-en');
    } else {
      const ja = el.getAttribute('data-champ-ja');
      if (ja) el.textContent = ja;
    }
  });
  const btn = document.getElementById('lang-toggle');
  if (btn) btn.textContent = lang === 'ja' ? '🌐 EN' : '🌐 JA';
  if (window._renderAll) window._renderAll();
  render();
}
function toggleLang() { applyLang(currentLang === 'ja' ? 'en' : 'ja'); }

// ── event data ────────────────────────────────────────────────────────────
const events     = EVENTS;
const userTeamId = FRIEND_TEAM_ID;
const _players   = PLAYERS;
const _DD_VER    = DD_VERSION;

// participantId → player 逆引きマップ（イベントアイコン用）
const pid2player = {};
_players.forEach(p => { if (p.pid) pid2player[p.pid] = p; });

// champion <img> タグ生成
function champImg(pid, cls) {
  const p = pid2player[pid];
  if (!p || !p.champName) return '';
  const sideCls = p.is_user ? ' user' : (p.teamId === userTeamId ? ' friend' : ' enemy');
  const src = `https://ddragon.leagueoflegends.com/cdn/${_DD_VER}/img/champion/${p.champName}.png`;
  return `<img class="ev-champ ${cls}${sideCls}" src="${src}" title="${p.champ}" loading="lazy">`;
}

// キラー + アシスト縦並びグループ
function killerGroupHtml(killerPid, assistPids) {
  const killer = champImg(killerPid, 'killer');
  const assistCol = (assistPids && assistPids.length > 0)
    ? `<div class="ev-assists-col">${assistPids.map(pid => champImg(pid, 'assist')).join('')}</div>`
    : '';
  return `<div class="ev-killer-group">${killer}${assistCol}</div>`;
}

// イベント行HTML生成
function buildEventHtml(e) {
  const sideClass = (e.teamId === userTeamId) ? 'friend' : (e.teamId ? 'enemy' : '');
  let iconsHtml = '';
  const labelText = currentLang === 'ja' ? e.text : (e.text_en || e.text);

  if (e.type === 'CHAMPION_KILL') {
    iconsHtml = killerGroupHtml(e.killerId, e.assistingParticipantIds) +
                `<span class="ev-verb">⚔️</span>` +
                champImg(e.victimId, 'victim');
  } else if (e.type === 'BUILDING_KILL') {
    const icon = (e.buildingType === 'INHIBITOR_BUILDING') ? '💎' : '🏰';
    iconsHtml = killerGroupHtml(e.killerId, e.assistingParticipantIds) +
                `<span class="ev-verb">${icon}</span>`;
  } else if (e.type === 'ELITE_MONSTER_KILL') {
    const icon = e.monsterType === 'BARON_NASHOR' ? '🐗' :
                 e.monsterType === 'DRAGON'       ? '🐉' : '👾';
    iconsHtml = champImg(e.killerId, 'killer') + `<span class="ev-verb">${icon}</span>`;
  }

  return `<div class="ev-row ${sideClass}">` +
         `<div class="ev-time">${e.time}</div>` +
         `<div class="ev-icons">${iconsHtml}</div>` +
         `<div class="ev-label">${escapeHtml(labelText)}</div>` +
         `</div>`;
}

const $q = document.getElementById('q');
const $team = document.getElementById('team');
const $type = document.getElementById('type');
const $events = document.getElementById('events');
const $count = document.getElementById('count');

function uniq(arr) {
  return Array.from(new Set(arr)).filter(Boolean).sort();
}

function buildTypeOptions() {
  const types = uniq(events.map(e => e.type));
  for (const t of types) {
    const opt = document.createElement('option');
    opt.value = t;
    opt.textContent = t;
    $type.appendChild(opt);
  }
}

function escapeHtml(str) {
  return String(str).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
}

function render() {
  const q = ($q.value || '').toLowerCase();
  const team = $team.value;
  const type = $type.value;

  const filtered = events.filter(e => {
    if (team && String(e.teamId) !== team) return false;
    if (type && e.type !== type) return false;
    if (q) {
      const hay = (e.time + " " + (e.team||"") + " " + (e.team_en||"") + " " + e.type + " " + e.text + " " + (e.text_en||"")).toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  $count.textContent = filtered.length;
  $events.innerHTML = "";

  for (const e of filtered) {
    $events.insertAdjacentHTML('beforeend', buildEventHtml(e));
  }
}

[$q, $team, $type].forEach(el => el.addEventListener('input', render));
[$team, $type].forEach(el => el.addEventListener('change', render));

buildTypeOptions();
render();

// ── Charts ─────────────────────────────────────────────────────────────────
(function() {
  const players      = PLAYERS;
  const friendTeamId = FRIEND_TEAM_ID;
  const DD_VER       = DD_VERSION;
  const gameDuration = GAME_DURATION;
  const goldFrames   = GOLD_FRAMES;

  // ── roundRect polyfill ────────────────────────────────────────────────────
  if (!CanvasRenderingContext2D.prototype.roundRect) {
    CanvasRenderingContext2D.prototype.roundRect = function(x, y, w, h, r) {
      r = Math.min(typeof r === 'number' ? r : (r[0] || 0), w / 2, h / 2);
      this.beginPath();
      this.moveTo(x + r, y);
      this.lineTo(x + w - r, y);
      this.quadraticCurveTo(x + w, y, x + w, y + r);
      this.lineTo(x + w, y + h - r);
      this.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
      this.lineTo(x + r, y + h);
      this.quadraticCurveTo(x, y + h, x, y + h - r);
      this.lineTo(x, y + r);
      this.quadraticCurveTo(x, y, x + r, y);
      this.closePath();
      return this;
    };
  }

  // ── ユーティリティ ────────────────────────────────────────────────────────
  function setupCanvas(canvas, w, h) {
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    return ctx;
  }

  function fmtNum(n) {
    return n >= 10000 ? (n / 1000).toFixed(1) + 'k' : String(n);
  }

  const COL = {
    text: '#9fb0cf', muted: 'rgba(158,176,207,0.45)', grid: 'rgba(255,255,255,0.05)',
    user: '#f0c040',
    kill: '#fbbf24', death: '#ff4d5a', assist: '#a78bfa',
    friendA: '#1245a8', friendB: '#3b8ef0',
    enemyA:  '#8b1a24', enemyB:  '#ff4d5a',
    tealA:   '#064a3c', tealB:   '#06d6a0',
    orangeA: '#4a2a00', orangeB: '#ff9500',
  };

  const ROW = 52, LABEL_W = 128;

  // ── チャンピオンアイコン プリロード ───────────────────────────────────────
  const champIcons = {};
  let iconsReady = false;
  const _names = [...new Set(players.map(p => p.champName).filter(Boolean))];
  let _loaded = 0;
  function _onIconLoad() {
    if (++_loaded === _names.length) { iconsReady = true; renderAll(); }
  }
  _names.forEach(name => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload  = () => { champIcons[name] = img; _onIconLoad(); };
    img.onerror = _onIconLoad;
    img.src = `https://ddragon.leagueoflegends.com/cdn/${DD_VER}/img/champion/${name}.png`;
  });
  if (_names.length === 0) iconsReady = true;

  // ── 丸アイコン描画 ────────────────────────────────────────────────────────
  function drawCircleIcon(ctx, champName, cx, cy, r) {
    ctx.save();
    ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.clip();
    const img = champIcons[champName];
    if (img) { ctx.drawImage(img, cx - r, cy - r, r * 2, r * 2); }
    else      { ctx.fill(); }
    ctx.restore();
  }

  function playerColor(p, isFriend) {
    return p.is_user ? COL.user : (isFriend ? '#c8d8f0' : '#f0b8bc');
  }

  function drawLabel(ctx, p, x, y, h) {
    const isFriend = p.teamId === friendTeamId;
    const iconR = 22;
    const iconCx = x - iconR - 6;
    const iconCy = y + h / 2;
    if (iconsReady) {
      ctx.fillStyle = isFriend ? '#1a3a6a' : '#5a1a20';
      drawCircleIcon(ctx, p.champName, iconCx, iconCy, iconR);
      // アイコン枠
      ctx.strokeStyle = p.is_user ? COL.user : (isFriend ? '#3b8ef0' : '#ff4d5a');
      ctx.lineWidth = p.is_user ? 2 : 1;
      ctx.beginPath(); ctx.arc(iconCx, iconCy, iconR, 0, Math.PI * 2); ctx.stroke();
    }
    ctx.fillStyle = playerColor(p, isFriend);
    ctx.font = (p.is_user ? '600 ' : '') + '10px system-ui,sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText(p.champ, iconCx - iconR - 4, iconCy + 4);
  }

  // ── 汎用 横棒チャート ─────────────────────────────────────────────────────
  function drawHBar(canvas, sorted, key, fmt, gradFriend, gradEnemy) {
    const W = canvas.parentElement.clientWidth - 24;
    const PAD = { t: 8, r: 56, b: 8, l: LABEL_W };
    const H = PAD.t + sorted.length * ROW + PAD.b;
    const ctx = setupCanvas(canvas, W, H);
    const chartW = W - PAD.l - PAD.r;
    const maxVal = Math.max(...sorted.map(p => p[key]), 1);

    sorted.forEach((p, i) => {
      const y = PAD.t + i * ROW;
      const bY = y + 8, bH = ROW - 14;
      const bw = Math.max((p[key] / maxVal) * chartW, p[key] > 0 ? 3 : 0);
      const isFriend = p.teamId === friendTeamId;

      drawLabel(ctx, p, PAD.l, bY, bH);

      // BG track
      ctx.fillStyle = 'rgba(255,255,255,0.03)';
      ctx.beginPath(); ctx.roundRect(PAD.l, bY, chartW, bH, 4); ctx.fill();

      if (bw > 0) {
        const [cA, cB] = isFriend ? gradFriend : gradEnemy;
        const grad = ctx.createLinearGradient(PAD.l, 0, PAD.l + bw, 0);
        grad.addColorStop(0, cA); grad.addColorStop(1, cB);
        ctx.fillStyle = grad;
        ctx.beginPath(); ctx.roundRect(PAD.l, bY, bw, bH, 4); ctx.fill();

        if (p.is_user) {
          ctx.shadowColor = COL.user; ctx.shadowBlur = 8;
          ctx.fillStyle = 'rgba(240,192,64,0.15)';
          ctx.beginPath(); ctx.roundRect(PAD.l, bY, bw, bH, 4); ctx.fill();
          ctx.shadowBlur = 0;
        }
      }

      ctx.fillStyle = COL.text;
      ctx.font = '11px system-ui,sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText(fmt(p[key]), PAD.l + bw + 6, bY + bH / 2 + 4);
    });
  }

  // ── ロリポップチャート（単一値比較）────────────────────────────────────────
  function drawLollipop(canvas, sorted, key, fmt, gradFriend, gradEnemy) {
    const W = canvas.parentElement.clientWidth - 24;
    const PAD = { t: 8, r: 64, b: 8, l: LABEL_W };
    const H = PAD.t + sorted.length * ROW + PAD.b;
    const ctx = setupCanvas(canvas, W, H);
    const chartW = W - PAD.l - PAD.r;
    const maxVal = Math.max(...sorted.map(p => p[key]), 1);

    sorted.forEach((p, i) => {
      const y    = PAD.t + i * ROW;
      const midY = y + ROW / 2;
      const isFriend = p.teamId === friendTeamId;
      const stemX = PAD.l + Math.max((p[key] / maxVal) * chartW, 0);
      const dotR  = p.is_user ? 12 : 10;

      drawLabel(ctx, p, PAD.l, y + 7, ROW - 14);

      // トラック（全幅・薄いライン）
      ctx.strokeStyle = 'rgba(255,255,255,0.05)';
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(PAD.l, midY); ctx.lineTo(PAD.l + chartW, midY); ctx.stroke();

      if (p[key] > 0) {
        // ステム（グラデーションライン）
        const [cA, cB] = isFriend ? gradFriend : gradEnemy;
        if (p.is_user) {
          ctx.strokeStyle = COL.user;
          ctx.lineWidth = 2;
        } else {
          const grad = ctx.createLinearGradient(PAD.l, 0, stemX, 0);
          grad.addColorStop(0, hexRgba(cA, 0.3));
          grad.addColorStop(1, hexRgba(cB, 0.9));
          ctx.strokeStyle = grad;
          ctx.lineWidth = 1.5;
        }
        ctx.beginPath(); ctx.moveTo(PAD.l, midY); ctx.lineTo(stemX, midY); ctx.stroke();

        // ドット
        if (p.is_user) { ctx.shadowColor = COL.user; ctx.shadowBlur = 10; }
        ctx.fillStyle = p.is_user ? COL.user : (isFriend ? gradFriend[1] : gradEnemy[1]);
        ctx.beginPath(); ctx.arc(stemX, midY, dotR, 0, Math.PI * 2); ctx.fill();
        ctx.shadowBlur = 0;

        // ドット外枠
        ctx.strokeStyle = p.is_user ? 'rgba(255,255,255,0.8)' : 'rgba(255,255,255,0.18)';
        ctx.lineWidth = p.is_user ? 1.5 : 1;
        ctx.beginPath(); ctx.arc(stemX, midY, dotR, 0, Math.PI * 2); ctx.stroke();
      }

      // 値ラベル
      ctx.fillStyle = p.is_user ? COL.user : COL.text;
      ctx.font = (p.is_user ? '600 ' : '') + '11px system-ui,sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText(fmt(p[key]), stemX + dotR + 6, midY + 4);
    });
  }

  // ── KDA 内訳（ダイバージング横棒: ← Deaths | K + A →）───────────────────
  function drawKDABreakdown(canvas) {
    const W = canvas.parentElement.clientWidth - 24;
    const PAD = { t: 28, r: 16, b: 8, l: LABEL_W };
    const H = PAD.t + players.length * ROW + PAD.b;
    const ctx = setupCanvas(canvas, W, H);
    const chartW = W - PAD.l - PAD.r;

    // maxD : maxKA の比率で左右幅を割り振り → 1:1スケール維持 + 最多デスが左端に届く
    const maxD  = Math.max(...players.map(p => p.d), 1);
    const maxKA = Math.max(...players.map(p => p.k + p.a), 1);
    const pixPerUnit = (chartW - 2) / (maxD + maxKA);
    const leftW  = Math.round(maxD  * pixPerUnit);  // デス側の幅
    const rightW = chartW - 2 - leftW;              // K+A側の幅
    const cX     = PAD.l + leftW;                   // ベースライン X

    // 凡例: 左側 "Deaths ←" / 右側 "→ K  A"
    ctx.fillStyle = COL.death;
    ctx.beginPath(); ctx.roundRect(cX - 80, 6, 12, 10, 3); ctx.fill();
    ctx.fillStyle = COL.muted; ctx.font = '10px system-ui,sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText(t('legend_deaths'), cX - 4, 15);

    [[COL.kill, t('legend_kills')], [COL.assist, t('legend_assists')]].forEach(([c, lbl], i) => {
      const lx = cX + 4 + i * 44;
      ctx.fillStyle = c;
      ctx.beginPath(); ctx.roundRect(lx, 6, 12, 10, 3); ctx.fill();
      ctx.fillStyle = COL.muted; ctx.textAlign = 'left';
      ctx.fillText(lbl, lx + 16, 15);
    });

    // 中心線（縦）
    ctx.strokeStyle = 'rgba(255,255,255,0.18)';
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(cX, PAD.t - 4); ctx.lineTo(cX, H - PAD.b); ctx.stroke();

    players.forEach((p, i) => {
      const y = PAD.t + i * ROW;
      const bY = y + 8, bH = ROW - 14;

      // チーム区切り線
      if (i > 0 && players[i - 1].teamId !== p.teamId) {
        ctx.strokeStyle = 'rgba(255,255,255,0.1)';
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(PAD.l, y - 2); ctx.lineTo(W - PAD.r, y - 2); ctx.stroke();
      }

      drawLabel(ctx, p, PAD.l, bY, bH);

      // ユーザー行 背景ハイライト
      if (p.is_user) {
        ctx.fillStyle = 'rgba(240,192,64,0.05)';
        ctx.fillRect(PAD.l, bY - 3, chartW, bH + 6);
      }

      // BG トラック（左・右）
      ctx.fillStyle = 'rgba(255,255,255,0.03)';
      ctx.beginPath(); ctx.roundRect(PAD.l, bY, leftW,   bH, [4, 0, 0, 4]); ctx.fill();
      ctx.beginPath(); ctx.roundRect(cX + 1, bY, rightW, bH, [0, 4, 4, 0]); ctx.fill();

      // Deaths（左向き）
      const dW = Math.round(p.d * pixPerUnit);
      if (dW > 0) {
        ctx.fillStyle = COL.death;
        ctx.beginPath(); ctx.roundRect(cX - dW, bY, dW, bH, [4, 0, 0, 4]); ctx.fill();
        if (dW > 16) {
          ctx.fillStyle = 'rgba(0,0,0,0.7)';
          ctx.font = 'bold 10px system-ui,sans-serif';
          ctx.textAlign = 'center';
          ctx.fillText(p.d, cX - dW / 2, bY + bH / 2 + 4);
        }
      }

      // Kills + Assists（右向き・積み上げ）
      const kW  = Math.round(p.k * pixPerUnit);
      const aW  = Math.round(p.a * pixPerUnit);
      const kaW = Math.min(kW + aW, rightW);
      if (kaW > 0) {
        ctx.save();
        ctx.beginPath(); ctx.roundRect(cX + 1, bY, kaW, bH, [0, 4, 4, 0]); ctx.clip();
        if (kW > 0) {
          ctx.fillStyle = COL.kill;
          ctx.fillRect(cX + 1, bY, kW, bH);
          if (kW > 16) {
            ctx.fillStyle = 'rgba(0,0,0,0.7)';
            ctx.font = 'bold 10px system-ui,sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(p.k, cX + 1 + kW / 2, bY + bH / 2 + 4);
          }
        }
        if (aW > 0) {
          ctx.fillStyle = COL.assist;
          ctx.fillRect(cX + 1 + kW, bY, aW, bH);
          if (aW > 16) {
            ctx.fillStyle = 'rgba(0,0,0,0.7)';
            ctx.font = 'bold 10px system-ui,sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(p.a, cX + 1 + kW + aW / 2, bY + bH / 2 + 4);
          }
        }
        ctx.restore();
      }
    });
  }

  // ── 散布図（与ダメ vs 被ダメ）────────────────────────────────────────────
  function drawScatter(canvas) {
    const W = canvas.parentElement.clientWidth - 24;
    const PAD = { t: 20, r: 30, b: 48, l: 64 };
    const H = 340;
    const ctx = setupCanvas(canvas, W, H);
    const chartW = W - PAD.l - PAD.r;
    const chartH = H - PAD.t - PAD.b;

    const maxDmg   = Math.max(...players.map(p => p.dmg),   1);
    const maxTaken = Math.max(...players.map(p => p.taken),  1);
    const midDmg   = maxDmg   / 2;
    const midTaken = maxTaken / 2;

    // グリッド
    ctx.strokeStyle = COL.grid;
    ctx.lineWidth = 1;
    [0.25, 0.5, 0.75, 1].forEach(f => {
      const gx = PAD.l + chartW * f;
      ctx.beginPath(); ctx.moveTo(gx, PAD.t); ctx.lineTo(gx, PAD.t + chartH); ctx.stroke();
      const gy = PAD.t + chartH * (1 - f);
      ctx.beginPath(); ctx.moveTo(PAD.l, gy); ctx.lineTo(PAD.l + chartW, gy); ctx.stroke();
    });

    // 中央値十字（薄め）
    ctx.strokeStyle = 'rgba(255,255,255,0.12)';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 4]);
    const midX = PAD.l + (midDmg / maxDmg) * chartW;
    const midY = PAD.t + chartH * (1 - midTaken / maxTaken);
    ctx.beginPath(); ctx.moveTo(midX, PAD.t); ctx.lineTo(midX, PAD.t + chartH); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(PAD.l, midY); ctx.lineTo(PAD.l + chartW, midY); ctx.stroke();
    ctx.setLineDash([]);

    // 象限ラベル
    const qlabels = [
      [PAD.l + 6, PAD.t + 14, t('q_tank'), 'rgba(255,77,90,0.5)'],
      [PAD.l + chartW - 80, PAD.t + 14, t('q_fighter'), 'rgba(251,191,36,0.5)'],
      [PAD.l + 6, PAD.t + chartH - 6, t('q_support'), 'rgba(158,176,207,0.4)'],
      [PAD.l + chartW - 68, PAD.t + chartH - 6, t('q_carry'), 'rgba(47,123,246,0.6)'],
    ];
    qlabels.forEach(([qx, qy, txt, c]) => {
      ctx.fillStyle = c;
      ctx.font = '600 10px system-ui,sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText(txt, qx, qy);
    });

    // 軸ラベル
    ctx.fillStyle = COL.muted;
    ctx.font = '10px system-ui,sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(t('axis_dmg_dealt'), PAD.l + chartW / 2, H - 8);
    ctx.save();
    ctx.translate(14, PAD.t + chartH / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText(t('axis_dmg_taken'), 0, 0);
    ctx.restore();

    // 軸目盛
    [0, 0.5, 1].forEach(f => {
      const gx = PAD.l + chartW * f;
      ctx.fillStyle = COL.muted;
      ctx.font = '9px system-ui,sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(fmtNum(Math.round(maxDmg * f)), gx, PAD.t + chartH + 14);
      const gy = PAD.t + chartH * (1 - f);
      ctx.textAlign = 'right';
      ctx.fillText(fmtNum(Math.round(maxTaken * f)), PAD.l - 5, gy + 4);
    });

    // ドット描画（自分以外先に描いて、自分を最前面に）
    const sorted = [...players].sort((a, b) => a.is_user - b.is_user);
    sorted.forEach(p => {
      const isFriend = p.teamId === friendTeamId;
      const cx = PAD.l + (p.dmg / maxDmg) * chartW;
      const cy = PAD.t + chartH * (1 - p.taken / maxTaken);
      const r = p.is_user ? 20 : 16;

      // グロー（自プレイヤー）— 光輪を先に描いてからアイコン
      if (p.is_user) {
        ctx.shadowColor = COL.user; ctx.shadowBlur = 14;
        ctx.fillStyle = COL.user;
        ctx.beginPath(); ctx.arc(cx, cy, r + 1, 0, Math.PI * 2); ctx.fill();
        ctx.shadowBlur = 0;
      }

      // アイコン（フォールバック: 塗り円）
      ctx.fillStyle = p.is_user ? COL.user : (isFriend ? '#2f7bf6' : '#ff4d5a');
      drawCircleIcon(ctx, p.champName, cx, cy, r);

      // 枠
      ctx.strokeStyle = p.is_user ? COL.user : (isFriend ? '#3b8ef0' : '#ff4d5a');
      ctx.lineWidth = p.is_user ? 2.5 : 1;
      ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.stroke();

      // ラベル
      ctx.fillStyle = p.is_user ? COL.user : COL.text;
      ctx.font = (p.is_user ? '600 ' : '') + '10px system-ui,sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText(p.champ, cx + r + 4, cy + 4);
    });
  }

  // ── レーダーチャート ──────────────────────────────────────────────────────
  function hexRgba(hex, a) {
    const n = parseInt(hex.replace('#', ''), 16);
    return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`;
  }

  // --- レーダー インタラクション ヘルパー ---
  const _radarState = new Map();
  const _RADAR_KEYS  = ['kda','dmg','gold','cs','vision','cc'];
  const _LEGEND_H    = 84;

  function _radarGeom(canvas) {
    const W      = canvas.parentElement.clientWidth - 24;
    const H      = 360;
    const cx     = W / 2;
    const maxR   = Math.min(W / 2 - 40, (H - _LEGEND_H - 20) / 2 - 20);
    const radius = Math.max(maxR, 60);
    const radarCy = _LEGEND_H / 2 + radius + 24;
    const N       = _RADAR_KEYS.length;
    const angles  = Array.from({length: N}, (_, i) => Math.PI * 2 * i / N - Math.PI / 2);
    return { W, H, cx, radarCy, radius, angles };
  }

  function _radarPolyPts(p, cx, radarCy, radius, angles, gMax) {
    return _RADAR_KEYS.map((key, i) => {
      const val = Math.min((p[key] || 0) / gMax[key], 1);
      return [cx + radius * val * Math.cos(angles[i]),
              radarCy + radius * val * Math.sin(angles[i])];
    });
  }

  function _ptInPoly(px, py, poly) {
    let inside = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      const [xi, yi] = poly[i], [xj, yj] = poly[j];
      if (((yi > py) !== (yj > py)) && px < (xj - xi) * (py - yi) / (yj - yi) + xi)
        inside = !inside;
    }
    return inside;
  }

  function _radarLegItems(canvas, n) {
    const { W, H } = _radarGeom(canvas);
    const legY = H - _LEGEND_H + 6;
    const colW = Math.floor(W / 3);
    return Array.from({length: n}, (_, pi) => ({
      iconR: 18,
      iconCx: (pi % 3) * colW + 8 + 18,
      iconCy: legY + Math.floor(pi / 3) * 36 + 18,
    }));
  }

  function _redrawRadar(canvas) {
    const s = _radarState.get(canvas);
    if (s) drawRadar(canvas, s.tp, s.ap);
  }

  function _setupRadarEvents(canvas) {
    function getHit(mx, my, s) {
      const items = _radarLegItems(canvas, s.tp.length);
      for (let pi = 0; pi < items.length; pi++) {
        const { iconCx, iconCy, iconR } = items[pi];
        if (Math.hypot(mx - iconCx, my - iconCy) <= iconR + 10) return pi;
      }
      const g = _radarGeom(canvas);
      const gMax = {};
      _RADAR_KEYS.forEach(k => {
        gMax[k] = Math.max(...s.ap.map(p => p[k] || 0), 1);
      });
      for (let pi = s.tp.length - 1; pi >= 0; pi--) {
        const poly = _radarPolyPts(s.tp[pi], g.cx, g.radarCy, g.radius, g.angles, gMax);
        if (_ptInPoly(mx, my, poly)) return pi;
      }
      return null;
    }

    canvas.addEventListener('mousemove', e => {
      const s = _radarState.get(canvas);
      if (!s) return;
      const r = canvas.getBoundingClientRect();
      const newH = s.fi !== null ? null : getHit(e.clientX - r.left, e.clientY - r.top, s);
      canvas.style.cursor = (newH !== null || s.fi !== null) ? 'pointer' : 'default';
      if (newH !== s.hi) { s.hi = newH; _redrawRadar(canvas); }
    });

    canvas.addEventListener('mouseleave', () => {
      const s = _radarState.get(canvas);
      if (s && s.hi !== null) { s.hi = null; _redrawRadar(canvas); }
      canvas.style.cursor = 'default';
    });

    function handleClick(mx, my) {
      const s = _radarState.get(canvas);
      if (!s) return;
      const hi = getHit(mx, my, s);
      if (hi !== null) {
        s.fi = s.fi === hi ? null : hi;
        s.hi = null;
        canvas.style.cursor = 'pointer';
        _redrawRadar(canvas);
      }
    }

    canvas.addEventListener('click', e => {
      const r = canvas.getBoundingClientRect();
      handleClick(e.clientX - r.left, e.clientY - r.top);
    });

    canvas.addEventListener('touchstart', e => {
      const s = _radarState.get(canvas);
      if (!s) return;
      const r   = canvas.getBoundingClientRect();
      const t   = e.touches[0];
      const hi  = getHit(t.clientX - r.left, t.clientY - r.top, s);
      if (hi !== null) {
        e.preventDefault();
        s.fi = s.fi === hi ? null : hi;
        _redrawRadar(canvas);
      }
    }, { passive: false });
  }

  function drawRadar(canvas, teamPlayers, allPlayers) {
    // state 初期化（初回のみ event listener セットアップ）
    if (!_radarState.has(canvas)) {
      _radarState.set(canvas, { tp: null, ap: null, fi: null, hi: null });
      _setupRadarEvents(canvas);
    }
    const state = _radarState.get(canvas);
    state.tp = teamPlayers;
    state.ap = allPlayers;
    const activeIdx = state.fi !== null ? state.fi : state.hi;  // focus > hover

    const METRICS = [
      { key: 'kda',    label: 'KDA'    },
      { key: 'dmg',    label: 'DMG'    },
      { key: 'gold',   label: 'Gold'   },
      { key: 'cs',     label: 'CS'     },
      { key: 'vision', label: 'Vision' },
      { key: 'cc',     label: 'CC'     },
    ];
    const N = METRICS.length;
    const W = canvas.parentElement.clientWidth - 24;
    const H = 360;
    const ctx = setupCanvas(canvas, W, H);
    const { cx, radarCy, radius, angles } = _radarGeom(canvas);

    const isFriendTeam = teamPlayers.length > 0 && teamPlayers[0].teamId === friendTeamId;
    const TEAM_COLORS = isFriendTeam
      ? ['#60b4ff', '#3b8ef0', '#1a6fd4', '#0d4aaa', '#082e7a']
      : ['#ff8080', '#ff4d5a', '#e02035', '#b01025', '#7a0015'];

    const gMax = {};
    METRICS.forEach(m => {
      gMax[m.key] = Math.max(...allPlayers.map(p => p[m.key] || 0), 1);
    });

    // グリッド同心多角形
    [0.25, 0.5, 0.75, 1.0].forEach(f => {
      ctx.beginPath();
      angles.forEach((a, i) => {
        const gx = cx + radius * f * Math.cos(a);
        const gy = radarCy + radius * f * Math.sin(a);
        i === 0 ? ctx.moveTo(gx, gy) : ctx.lineTo(gx, gy);
      });
      ctx.closePath();
      ctx.strokeStyle = COL.grid; ctx.lineWidth = 1; ctx.stroke();
    });

    // 軸線 + ラベル
    angles.forEach((a, i) => {
      const ex = cx + radius * Math.cos(a), ey = radarCy + radius * Math.sin(a);
      ctx.strokeStyle = COL.grid; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(cx, radarCy); ctx.lineTo(ex, ey); ctx.stroke();
      const lx = cx + (radius + 18) * Math.cos(a);
      const ly = radarCy + (radius + 18) * Math.sin(a);
      const cosA = Math.cos(a), sinA = Math.sin(a);
      ctx.fillStyle = COL.muted; ctx.font = '10px system-ui,sans-serif';
      ctx.textAlign    = Math.abs(cosA) < 0.15 ? 'center' : cosA > 0 ? 'left' : 'right';
      ctx.textBaseline = Math.abs(sinA) < 0.15 ? 'middle' : sinA > 0 ? 'top'  : 'bottom';
      ctx.fillText(METRICS[i].label, lx, ly);
      ctx.textBaseline = 'alphabetic';
    });

    // ポリゴン（ユーザーを最前面）
    [...teamPlayers].sort((a, b) => a.is_user - b.is_user).forEach(p => {
      const origIdx  = teamPlayers.indexOf(p);
      const isUser   = p.is_user;
      const isActive = activeIdx === null || origIdx === activeIdx;
      const color    = isUser ? COL.user : TEAM_COLORS[origIdx % TEAM_COLORS.length];
      const pts = METRICS.map((m, i) => {
        const val = Math.min((p[m.key] || 0) / gMax[m.key], 1);
        return [cx + radius * val * Math.cos(angles[i]),
                radarCy + radius * val * Math.sin(angles[i])];
      });

      // 塗り
      ctx.beginPath();
      pts.forEach(([px, py], i) => i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py));
      ctx.closePath();
      ctx.fillStyle = hexRgba(color, isActive ? 0.18 : 0.03);
      ctx.fill();

      // ライン
      if (isUser && isActive) { ctx.shadowColor = COL.user; ctx.shadowBlur = 10; }
      ctx.strokeStyle = isActive ? color : hexRgba(color, 0.18);
      ctx.lineWidth = isActive ? (isUser ? 2.5 : 2.0) : 0.8;
      ctx.beginPath();
      pts.forEach(([px, py], i) => i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py));
      ctx.closePath();
      ctx.stroke();
      ctx.shadowBlur = 0;
    });

    // 凡例（下部・クリック可）
    const legY = H - _LEGEND_H + 6;
    const colW = Math.floor(W / 3);
    teamPlayers.forEach((p, pi) => {
      const lx   = (pi % 3) * colW + 8;
      const ly   = legY + Math.floor(pi / 3) * 36;
      const isUser   = p.is_user;
      const isActive = activeIdx === null || pi === activeIdx;
      const color    = isUser ? COL.user : TEAM_COLORS[pi % TEAM_COLORS.length];
      const iconR = 18, iconCx = lx + iconR, iconCy = ly + iconR;

      ctx.globalAlpha = isActive ? 1 : 0.3;
      ctx.fillStyle = isFriendTeam ? '#1a3a6a' : '#5a1a20';
      drawCircleIcon(ctx, p.champName, iconCx, iconCy, iconR);
      ctx.strokeStyle = color;
      ctx.lineWidth = isUser ? 2 : 1;
      ctx.beginPath(); ctx.arc(iconCx, iconCy, iconR, 0, Math.PI * 2); ctx.stroke();

      ctx.fillStyle = isUser ? COL.user : COL.text;
      ctx.font = (isUser ? '600 ' : '') + '10px system-ui,sans-serif';
      ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
      ctx.fillText(p.champ, iconCx + iconR + 4, iconCy);
      ctx.textBaseline = 'alphabetic';
      ctx.globalAlpha = 1;
    });
  }

  // ── チームゴールドリード 推移 ─────────────────────────────────────────────
  function drawGoldDiff(canvas) {
    if (!goldFrames || goldFrames.length < 2) return;
    const W = canvas.parentElement.clientWidth - 24;
    const H = 240;
    const ctx = setupCanvas(canvas, W, H);

    const PAD = { l: 68, r: 24, t: 28, b: 34 };
    const cW = W - PAD.l - PAD.r;
    const cH = H - PAD.t - PAD.b;
    const maxAbs = Math.max(...goldFrames.map(f => Math.abs(f.diff)), 1000);
    const maxT   = goldFrames[goldFrames.length - 1].t;

    const tx = t => PAD.l + (t / maxT) * cW;
    const ty = d => PAD.t + cH / 2 - (d / maxAbs) * (cH * 0.46);
    const zeroY = ty(0);

    // 背景グリッド横線 (±25%, ±50%, 0)
    ctx.lineWidth = 0.5;
    [-0.5, -0.25, 0, 0.25, 0.5].forEach(ratio => {
      ctx.strokeStyle = ratio === 0 ? 'rgba(255,255,255,0.12)' : COL.grid;
      const y = PAD.t + cH / 2 - ratio * cH * 0.46;
      ctx.beginPath(); ctx.moveTo(PAD.l, y); ctx.lineTo(PAD.l + cW, y); ctx.stroke();
    });

    // 垂直グリッド (5分刻み)
    ctx.strokeStyle = COL.grid; ctx.lineWidth = 0.5;
    for (let m = 5; m * 60 < maxT; m += 5) {
      const x = tx(m * 60);
      ctx.beginPath(); ctx.moveTo(x, PAD.t); ctx.lineTo(x, PAD.t + cH); ctx.stroke();
    }

    // 塗り面積パス（ゼロラインで閉じる）
    const areaPath = new Path2D();
    areaPath.moveTo(tx(goldFrames[0].t), zeroY);
    goldFrames.forEach(f => areaPath.lineTo(tx(f.t), ty(f.diff)));
    areaPath.lineTo(tx(maxT), zeroY);
    areaPath.closePath();

    // 上半分クリップ（味方リード = 青）
    ctx.save();
    ctx.beginPath(); ctx.rect(PAD.l, PAD.t, cW, zeroY - PAD.t); ctx.clip();
    ctx.fillStyle = hexRgba(COL.friendB, 0.22);
    ctx.fill(areaPath);
    ctx.restore();

    // 下半分クリップ（敵リード = 赤）
    ctx.save();
    ctx.beginPath(); ctx.rect(PAD.l, zeroY, cW, PAD.t + cH - zeroY); ctx.clip();
    ctx.fillStyle = hexRgba(COL.enemyB, 0.22);
    ctx.fill(areaPath);
    ctx.restore();

    // ゴールドリードライン
    ctx.beginPath();
    goldFrames.forEach((f, i) =>
      i === 0 ? ctx.moveTo(tx(f.t), ty(f.diff)) : ctx.lineTo(tx(f.t), ty(f.diff))
    );
    ctx.strokeStyle = COL.friendB; ctx.lineWidth = 2; ctx.stroke();

    // X軸ラベル（5分刻み）
    ctx.fillStyle = COL.text; ctx.font = '10px system-ui,sans-serif'; ctx.textAlign = 'center';
    for (let m = 0; m * 60 <= maxT; m += 5)
      ctx.fillText(m + 'm', tx(m * 60), H - 10);

    // Y軸ラベル
    ctx.textAlign = 'right';
    [
      [maxAbs,  PAD.t + 10,         COL.friendB],
      [0,       zeroY + 4,          COL.text],
      [-maxAbs, PAD.t + cH - 2,     COL.enemyB],
    ].forEach(([v, y, col]) => {
      ctx.fillStyle = col;
      ctx.fillText((v > 0 ? '+' : '') + fmtNum(v), PAD.l - 6, y);
    });

    // 凡例ラベル
    ctx.textAlign = 'left'; ctx.font = '11px system-ui,sans-serif';
    ctx.fillStyle = COL.friendB; ctx.fillText(t('ally_lead'),  PAD.l + 6, PAD.t + 14);
    ctx.fillStyle = COL.enemyB;  ctx.fillText(t('enemy_lead'), PAD.l + 6, PAD.t + cH - 6);
  }

  // ── 描画実行 ───────────────────────────────────────────────────────────────
  function renderAll() {
    drawKDABreakdown(document.getElementById('chart-kda-breakdown'));
    drawLollipop(document.getElementById('chart-kda-ratio'),
      [...players].sort((a,b)=>b.kda-a.kda),   'kda',   v=>v.toFixed(2),
      [COL.friendA, COL.friendB], [COL.enemyA, COL.enemyB]);
    drawLollipop(document.getElementById('chart-dmg'),
      [...players].sort((a,b)=>b.dmg-a.dmg),   'dmg',   fmtNum,
      [COL.friendA, COL.friendB], [COL.enemyA, COL.enemyB]);
    drawLollipop(document.getElementById('chart-gold'),
      [...players].sort((a,b)=>b.gold-a.gold),  'gold',  fmtNum,
      [COL.friendA, COL.friendB], [COL.enemyA, COL.enemyB]);
    drawLollipop(document.getElementById('chart-cs'),
      [...players].sort((a,b)=>b.cs-a.cs),     'cs',    String,
      [COL.tealA, COL.tealB],   [COL.orangeA, COL.orangeB]);
    drawLollipop(document.getElementById('chart-vision'),
      [...players].sort((a,b)=>b.vision-a.vision), 'vision', String,
      [COL.tealA, COL.tealB],   [COL.orangeA, COL.orangeB]);
    drawLollipop(document.getElementById('chart-cc'),
      [...players].sort((a,b)=>b.cc-a.cc),     'cc',    v=>v+'s',
      [COL.tealA, COL.tealB],   [COL.orangeA, COL.orangeB]);
    drawScatter(document.getElementById('chart-scatter'));
    const friendPs = players.filter(p => p.teamId === friendTeamId);
    const enemyPs  = players.filter(p => p.teamId !== friendTeamId);
    drawRadar(document.getElementById('chart-radar-friend'), friendPs, players);
    drawRadar(document.getElementById('chart-radar-enemy'),  enemyPs,  players);
    drawLollipop(document.getElementById('chart-kp'),
      [...players].sort((a, b) => b.kp - a.kp),
      'kp', v => (v * 100).toFixed(0) + '%',
      [COL.friendA, COL.friendB], [COL.enemyA, COL.enemyB]);
    drawLollipop(document.getElementById('chart-dead'),
      [...players].sort((a, b) => b.dead_s - a.dead_s),
      'dead_s', v => ((v / gameDuration) * 100).toFixed(0) + '%',
      [COL.enemyA, COL.enemyB], [COL.friendA, COL.friendB]);
    drawGoldDiff(document.getElementById('chart-gold-diff'));
  }

  window._renderAll = renderAll;
  requestAnimationFrame(renderAll);

  let _rt;
  window.addEventListener('resize', () => {
    clearTimeout(_rt);
    _rt = setTimeout(renderAll, 150);
  });
})();
