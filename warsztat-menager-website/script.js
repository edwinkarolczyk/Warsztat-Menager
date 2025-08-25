
// Warsztat Menager Website – script.js
document.addEventListener('DOMContentLoaded', () => {
  const year = document.querySelector('#year');
  if (year) year.textContent = new Date().getFullYear();

  // Smooth anchors (already via CSS), highlight active link
  const links = document.querySelectorAll('a.navlink');
  const sections = [...document.querySelectorAll('section[id]')];
  const obs = new IntersectionObserver((entries)=>{
    entries.forEach(e=>{
      if(e.isIntersecting){
        links.forEach(l=> l.classList.toggle('active', l.getAttribute('href') === '#'+e.target.id));
      }
    })
  }, {rootMargin: '-50% 0px -49% 0px'});
  sections.forEach(s=>obs.observe(s));
});
