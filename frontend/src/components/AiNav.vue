<template>
  <div class="page-head">
    <h1>KI-Generator <span class="badge neutral" style="vertical-align: middle">optional</span></h1>
    <p>
      Neue Fragen aus Vorlesungsmaterial erzeugen. Generierte Fragen müssen geprüft und freigegeben werden,
      danach stehen sie in der <router-link to="/bank">Fragenbank</router-link> zum Export bereit.
    </p>
  </div>
  <nav class="subnav">
    <router-link to="/upload">1 · Material hochladen</router-link>
    <router-link to="/generate">2 · Fragen generieren</router-link>
    <router-link to="/review">3 · Prüfen &amp; freigeben</router-link>
  </nav>
</template>
