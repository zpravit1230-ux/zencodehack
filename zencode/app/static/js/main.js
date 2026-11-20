// BrandGuard AI Vanilla JS Utilities
document.addEventListener('DOMContentLoaded', () => {
  // Auto-fill demo credentials when clicked
  document.querySelectorAll('.demo-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      const email = pill.getAttribute('data-email');
      const pass = pill.getAttribute('data-pass');
      const emailInput = document.getElementById('email');
      const passInput = document.getElementById('password');
      if (emailInput && passInput) {
        emailInput.value = email;
        passInput.value = pass;
        emailInput.focus();
      }
    });
  });

  // Initialize Dual-Panel Review Workspace if present
  initReviewWorkspace();
});

function initReviewWorkspace() {
  const workspace = document.getElementById('review-workspace');
  if (!workspace) return;

  const contentId = workspace.getAttribute('data-content-id');
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || 
                    document.querySelector('input[name="csrf_token"]')?.value;

  // 1. Page Navigation
  let currentPage = 1;
  const pageNodes = document.querySelectorAll('.doc-page-container');
  const totalPages = pageNodes.length;
  const pageNumDisplay = document.getElementById('current-page-display');
  const pageSelect = document.getElementById('page-jump-select');
  const prevBtn = document.getElementById('prev-page-btn');
  const nextBtn = document.getElementById('next-page-btn');

  function renderPage(pNum) {
    currentPage = Math.max(1, Math.min(totalPages, pNum));
    pageNodes.forEach(node => {
      if (parseInt(node.getAttribute('data-page-num')) === currentPage) {
        node.style.display = 'block';
      } else {
        node.style.display = 'none';
      }
    });
    if (pageNumDisplay) pageNumDisplay.textContent = currentPage;
    if (pageSelect) pageSelect.value = currentPage;
    if (prevBtn) prevBtn.disabled = (currentPage <= 1);
    if (nextBtn) nextBtn.disabled = (currentPage >= totalPages);
  }

  if (prevBtn) prevBtn.addEventListener('click', () => renderPage(currentPage - 1));
  if (nextBtn) nextBtn.addEventListener('click', () => renderPage(currentPage + 1));
  if (pageSelect) pageSelect.addEventListener('change', (e) => renderPage(parseInt(e.target.value)));

  // Initial render
  renderPage(1);

  // 2. View Mode Toggle (Original vs Corrected Live Preview)
  const tabOriginal = document.getElementById('tab-view-original');
  const tabCorrected = document.getElementById('tab-view-corrected');
  const viewOriginalWrap = document.getElementById('view-original-wrap');
  const viewCorrectedWrap = document.getElementById('view-corrected-wrap');

  if (tabOriginal && tabCorrected && viewOriginalWrap && viewCorrectedWrap) {
    tabOriginal.addEventListener('click', () => {
      tabOriginal.classList.add('btn-primary');
      tabOriginal.classList.remove('btn-secondary');
      tabCorrected.classList.add('btn-secondary');
      tabCorrected.classList.remove('btn-primary');
      viewOriginalWrap.style.display = 'block';
      viewCorrectedWrap.style.display = 'none';
    });

    tabCorrected.addEventListener('click', () => {
      tabCorrected.classList.add('btn-primary');
      tabCorrected.classList.remove('btn-secondary');
      tabOriginal.classList.add('btn-secondary');
      tabOriginal.classList.remove('btn-primary');
      viewOriginalWrap.style.display = 'none';
      viewCorrectedWrap.style.display = 'block';
    });
  }

  // 3. Issue Card Click -> Scroll & Highlight snippet on corresponding page
  document.querySelectorAll('.issue-card').forEach(card => {
    card.addEventListener('click', (e) => {
      if (e.target.tagName === 'BUTTON' || e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

      const issueId = card.getAttribute('data-issue-id');
      const targetPage = parseInt(card.getAttribute('data-page-num')) || 1;
      
      // Jump to page
      renderPage(targetPage);

      // Highlight corresponding mark
      document.querySelectorAll('mark.issue-highlight').forEach(m => m.classList.remove('active'));
      document.querySelectorAll('.issue-card').forEach(c => c.classList.remove('active-issue'));

      card.classList.add('active-issue');
      const targetMark = document.querySelector(`mark.issue-highlight[data-issue-id="${issueId}"]`);
      if (targetMark) {
        targetMark.classList.add('active');
        targetMark.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    });
  });

  // 4. Clicking Highlight in text -> Scroll to issue card on right
  document.querySelectorAll('mark.issue-highlight').forEach(mark => {
    mark.addEventListener('click', () => {
      const issueId = mark.getAttribute('data-issue-id');
      document.querySelectorAll('mark.issue-highlight').forEach(m => m.classList.remove('active'));
      mark.classList.add('active');

      const card = document.querySelector(`.issue-card[data-issue-id="${issueId}"]`);
      if (card) {
        document.querySelectorAll('.issue-card').forEach(c => c.classList.remove('active-issue'));
        card.classList.add('active-issue');
        card.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    });
  });

  // 5. Intelligent Suggestion Actions (Accept / Reject / Edit / Comment)
  workspace.addEventListener('click', async (e) => {
    const acceptBtn = e.target.closest('.btn-action-accept');
    const rejectBtn = e.target.closest('.btn-action-reject');
    const editBtn = e.target.closest('.btn-action-edit');
    const commentBtn = e.target.closest('.btn-action-comment');

    if (acceptBtn) {
      const issueId = acceptBtn.getAttribute('data-issue-id');
      await handleAccept(contentId, issueId, csrfToken);
    } else if (rejectBtn) {
      const issueId = rejectBtn.getAttribute('data-issue-id');
      await handleReject(contentId, issueId, csrfToken);
    } else if (editBtn) {
      const issueId = editBtn.getAttribute('data-issue-id');
      await handleEdit(contentId, issueId, csrfToken);
    } else if (commentBtn) {
      const issueId = commentBtn.getAttribute('data-issue-id');
      await handleComment(contentId, issueId, csrfToken);
    }
  });

  // 6. Category & Severity Filters
  const filterPills = document.querySelectorAll('.filter-pill');
  filterPills.forEach(pill => {
    pill.addEventListener('click', () => {
      filterPills.forEach(p => p.classList.remove('btn-primary'));
      pill.classList.add('btn-primary');
      const filterType = pill.getAttribute('data-filter');

      document.querySelectorAll('.issue-card').forEach(card => {
        if (filterType === 'all') {
          card.style.display = 'block';
        } else if (filterType === 'critical') {
          card.style.display = card.classList.contains('severity-critical') || card.classList.contains('severity-serious') ? 'block' : 'none';
        } else if (filterType === 'high') {
          card.style.display = card.classList.contains('severity-high') ? 'block' : 'none';
        } else if (filterType === 'medium') {
          card.style.display = card.classList.contains('severity-medium') || card.classList.contains('severity-warning') ? 'block' : 'none';
        } else if (filterType === 'low') {
          card.style.display = card.classList.contains('severity-low') || card.classList.contains('severity-info') ? 'block' : 'none';
        } else if (filterType === 'open') {
          card.style.display = card.getAttribute('data-status') === 'Open' ? 'block' : 'none';
        } else if (filterType === 'resolved') {
          card.style.display = card.getAttribute('data-status') !== 'Open' ? 'block' : 'none';
        }
      });
    });
  });
}

async function handleAccept(contentId, issueId, csrfToken) {
  try {
    const res = await fetch(`/content/${contentId}/issue/${issueId}/accept`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      }
    });
    const data = await res.json();
    if (data.success) {
      updateIssueCardUI(issueId, 'Accepted', '#15803d');
      updateScoresUI(data.quality_score, data.compliance_score);
      updateMarkUI(issueId, data.replacement);
      showToast('✓ Suggestion accepted and applied to document preview.');
    }
  } catch (err) {
    console.error('Accept error:', err);
  }
}

async function handleReject(contentId, issueId, csrfToken) {
  try {
    const res = await fetch(`/content/${contentId}/issue/${issueId}/reject`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      }
    });
    const data = await res.json();
    if (data.success) {
      updateIssueCardUI(issueId, 'Rejected', '#b91c1c');
      updateScoresUI(data.quality_score, data.compliance_score);
      showToast('Suggestion rejected. Original content retained.');
    }
  } catch (err) {
    console.error('Reject error:', err);
  }
}

async function handleEdit(contentId, issueId, csrfToken) {
  const card = document.querySelector(`.issue-card[data-issue-id="${issueId}"]`);
  const currentSuggestion = card.querySelector('.suggestion-text')?.textContent || '';
  const userInput = prompt('Modify the suggested correction before applying:', currentSuggestion);
  if (userInput === null || !userInput.trim()) return;

  try {
    const res = await fetch(`/content/${contentId}/issue/${issueId}/edit`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      body: JSON.stringify({ custom_text: userInput.trim() })
    });
    const data = await res.json();
    if (data.success) {
      updateIssueCardUI(issueId, 'Modified', '#1d4ed8');
      const suggEl = card.querySelector('.suggestion-text');
      if (suggEl) suggEl.textContent = userInput.trim();
      updateScoresUI(data.quality_score, data.compliance_score);
      updateMarkUI(issueId, userInput.trim());
      showToast('✓ Custom correction applied to document.');
    }
  } catch (err) {
    console.error('Edit error:', err);
  }
}

async function handleComment(contentId, issueId, csrfToken) {
  const card = document.querySelector(`.issue-card[data-issue-id="${issueId}"]`);
  const commentInput = card.querySelector('.reviewer-comment-input');
  const commentText = commentInput ? commentInput.value.trim() : '';

  try {
    const res = await fetch(`/content/${contentId}/issue/${issueId}/comment`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      body: JSON.stringify({ comment: commentText })
    });
    const data = await res.json();
    if (data.success) {
      showToast('Reviewer note saved.');
    }
  } catch (err) {
    console.error('Comment error:', err);
  }
}

function updateIssueCardUI(issueId, status, color) {
  const card = document.querySelector(`.issue-card[data-issue-id="${issueId}"]`);
  if (!card) return;
  card.setAttribute('data-status', status);
  const badge = card.querySelector('.issue-status-badge');
  if (badge) {
    badge.textContent = status;
    badge.style.backgroundColor = color;
    badge.style.color = '#ffffff';
  }
}

function updateScoresUI(quality, compliance) {
  const qEl = document.getElementById('metric-quality-score');
  const cEl = document.getElementById('metric-compliance-score');
  if (qEl) qEl.textContent = quality;
  if (cEl) cEl.textContent = compliance + '%';
}

function updateMarkUI(issueId, replacement) {
  const mark = document.querySelector(`mark.issue-highlight[data-issue-id="${issueId}"]`);
  if (mark) {
    mark.classList.add('accepted');
    mark.title = `Applied fix: ${replacement}`;
  }
  const liveCorrectedPreview = document.getElementById('live-corrected-text-body');
  if (liveCorrectedPreview && mark) {
    liveCorrectedPreview.textContent = liveCorrectedPreview.textContent.replace(mark.textContent, replacement);
  }
}

function showToast(msg) {
  let toast = document.getElementById('brandguard-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'brandguard-toast';
    toast.style.cssText = 'position:fixed;bottom:24px;right:24px;background:#1A1A1A;color:#FFFFFF;padding:12px 20px;border-radius:6px;box-shadow:0 4px 12px rgba(0,0,0,0.15);font-size:0.875rem;z-index:9999;transition:opacity 0.3s ease;';
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.style.opacity = '1';
  setTimeout(() => { toast.style.opacity = '0'; }, 3000);
}
