// Este script consolida toda a lógica JavaScript do base.html para melhor organização e cache.

document.addEventListener('DOMContentLoaded', function() {

    // --- ANTI-TRADUTOR (Bloqueia o Chrome de traduzir a tela para o Inglês) ---
    document.documentElement.lang = 'pt-BR';
    document.documentElement.setAttribute('translate', 'no');
    if (!document.querySelector('meta[name="google"]')) {
        const meta = document.createElement('meta');
        meta.name = 'google';
        meta.content = 'notranslate';
        document.head.appendChild(meta);
    }

    const body = document.body;

    // --- ESTILIZAÇÃO PREMIUM GLOBAL (SWEETALERT2) ---
    // Inspirado em totens modernos (McDonalds, Burger King)
    const swalStyles = document.createElement('style');
    swalStyles.innerHTML = `
        div.swal2-popup:not(.swal2-toast) {
            font-family: 'Nunito', 'Segoe UI', system-ui, sans-serif !important;
            border-radius: 16px !important;
        }
        .dark-mode div.swal2-popup:not(.swal2-toast) {
            background: #1e293b !important;
            color: #f8fafc !important;
        }
        .dark-mode div.swal2-popup:not(.swal2-toast) h2.swal2-title {
            color: #ffffff !important;
        }
        .dark-mode div.swal2-popup:not(.swal2-toast) div.swal2-html-container {
            color: #cbd5e1 !important;
        }

        /* --- MODO KIOSK (GIGANTE / FAST-FOOD STYLE PARA TABLET) --- */
        .kiosk-mode div.swal2-popup:not(.swal2-toast) {
            border-radius: 28px !important;
            padding: 2rem 1.5rem !important;
            box-shadow: 0 25px 60px rgba(0,0,0,0.4) !important;
        }
        .kiosk-mode div.swal2-popup:not(.swal2-toast) h2.swal2-title {
            font-size: 2.2rem !important;
            font-weight: 900 !important;
            letter-spacing: -1px !important;
            margin-bottom: 0.5rem !important;
            text-transform: uppercase !important;
        }
        .kiosk-mode div.swal2-popup:not(.swal2-toast) div.swal2-html-container {
            font-size: 1.2rem !important;
            font-weight: 600 !important;
            line-height: 1.4 !important;
        }
        .kiosk-mode div.swal2-popup:not(.swal2-toast) .swal2-actions {
            margin-top: 1.5rem !important;
            gap: 15px !important;
            width: 100% !important;
            padding: 0 1rem !important;
            box-sizing: border-box !important;
        }
        .kiosk-mode div.swal2-popup:not(.swal2-toast) button.swal2-styled {
            border-radius: 50px !important;
            font-weight: 900 !important;
            font-size: 1.4rem !important;
            padding: 18px 30px !important;
            letter-spacing: 1px !important;
            text-transform: uppercase !important;
            box-shadow: 0 10px 25px rgba(0,0,0,0.15) !important;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
            width: 100% !important;
        }
        .kiosk-mode div.swal2-popup:not(.swal2-toast) button.swal2-styled:hover {
            transform: translateY(-4px) !important;
            box-shadow: 0 15px 35px rgba(0,0,0,0.25) !important;
        }
        .kiosk-mode div.swal2-popup:not(.swal2-toast) button.swal2-styled:active {
            transform: translateY(2px) scale(0.96) !important;
        }
        .kiosk-mode div.swal2-popup:not(.swal2-toast) .swal2-icon {
            width: 6em !important;
            height: 6em !important;
            margin: 1em auto 1em !important;
            border-width: 5px !important;
        }
        .kiosk-mode div.swal2-popup:not(.swal2-toast) .swal2-icon .swal2-icon-content {
            font-size: 4.5em !important;
            font-weight: bold !important;
        }
    `;
    document.head.appendChild(swalStyles);

    // --- Kiosk Mode Detection (Smart Cart IoT) ---
    // Detecta se estamos acessando pelo Tablet do Carrinho Inteligente
    const urlParams = new URLSearchParams(window.location.search);
    
    // Escape Hatch: Permite desativar o Kiosk manualmente caso precise de manutenção (URL: ?kiosk=0)
    if (urlParams.get('kiosk') === '0' || urlParams.get('kiosk') === 'false') {
        localStorage.removeItem('kiosk_mode'); // Remove a trava permanente do PC
        sessionStorage.removeItem('kiosk_mode');
        sessionStorage.removeItem('kiosk_locked');
        body.classList.remove('kiosk-mode');
    }
    // Ativa o modo Kiosk temporário via URL (ex: QR Code no celular)
    else if (urlParams.get('kiosk') === '1' || urlParams.get('kiosk') === 'true') {
        body.classList.add('kiosk-mode');
        sessionStorage.setItem('kiosk_mode', 'true');
    } 
    // Se acessou a rota principal do Kiosk diretamente
    else if (window.location.pathname === '/kiosk') {
        body.classList.add('kiosk-mode');
    }
    // Mantém o visual do kiosk apenas enquanto estiver em uma tela do kiosk.
    else if (window.location.pathname === '/kiosk' || urlParams.get('kiosk') === '1' || urlParams.get('kiosk') === 'true') {
        body.classList.add('kiosk-mode');
    }
    // Ao abrir o sistema normalmente, sempre retorna ao dashboard.
    else if (window.location.pathname === '/' || window.location.pathname === '/dashboard') {
        localStorage.removeItem('kiosk_mode');
        sessionStorage.removeItem('kiosk_mode');
        sessionStorage.removeItem('kiosk_locked');
        body.classList.remove('kiosk-mode');
    }

    // --- KIOSK SUCCESS INTERCEPTOR (URL PARAMS) ---
    if (urlParams.get('kiosk_success') === 'saida') {
        let usuario = urlParams.get('usuario');
        if (!usuario || usuario === 'None' || usuario === 'null') usuario = 'Usuário';
        let slots = urlParams.get('slots');
        if (!slots || slots === 'None' || slots === 'null') slots = 'Qualquer';
        
        Swal.fire({
            icon: 'success',
            title: 'Porta Liberada!',
            html: `<div style="font-size: 1.2rem; color: #cbd5e1; margin-bottom: 15px;">Saída confirmada para <b>${usuario}</b>.</div>
                   <div style="background: rgba(16, 185, 129, 0.1); border: 2px solid rgba(16, 185, 129, 0.3); border-radius: 20px; padding: 20px; margin-bottom: 20px;">
                       <span style="color: #94a3b8; font-size: 1rem; font-weight: 800; text-transform: uppercase; letter-spacing: 2px;">Endereços para Retirar</span><br>
                       <div style="color: #10b981; font-size: 2.8rem; font-weight: 900; letter-spacing: 2px; margin-top: 5px; word-break: break-word; line-height: 1.1;">${slots}</div>
                   </div>
                   <div style="background: #ef4444; color: white; border-radius: 16px; padding: 18px; font-weight: 900; font-size: 1.4rem; letter-spacing: 1px; box-shadow: 0 10px 30px rgba(239, 68, 68, 0.4); animation: piscarVermelho 1.5s infinite; text-align: center;">
                       POR FAVOR, FECHE A PORTA
                   </div>
                   <style>@keyframes piscarVermelho { 0% { transform: scale(1); } 50% { transform: scale(1.02); } 100% { transform: scale(1); } }</style>`,
            showConfirmButton: true, 
            confirmButtonText: 'JÁ FECHEI A PORTA', 
            confirmButtonColor: '#10b981', 
            allowOutsideClick: false, 
            backdrop: `rgba(15, 23, 42, 0.95)`
        }).then(() => {
            window.history.replaceState({}, document.title, window.location.pathname);
        });
    }

    // --- Botão Profissional "Fixar Modo Totem" no Menu do Usuário ---
    const userMenu = document.querySelector('.dropdown-menu');
    if (userMenu && !document.getElementById('btn-fixar-totem') && !body.classList.contains('kiosk-mode')) {
        const btnTotem = document.createElement('a');
        btnTotem.id = 'btn-fixar-totem';
        btnTotem.href = '#';
        btnTotem.innerHTML = '<span class="material-icons-round" style="color: #3b82f6;">tv</span> Fixar Modo Totem';
        
        btnTotem.addEventListener('click', (e) => {
            e.preventDefault();
            if(typeof Swal !== 'undefined') {
                Swal.fire({
                    title: 'Ativar Modo Totem Fixo?',
                    text: 'Esta máquina ficará travada na tela de Autoatendimento. (Para destravar no futuro, acesse o link com /?kiosk=0)',
                    icon: 'warning',
                    showCancelButton: true,
                    confirmButtonColor: '#3b82f6',
                    cancelButtonColor: '#64748b',
                    confirmButtonText: 'SIM, TRAVAR MÁQUINA',
                    cancelButtonText: 'CANCELAR'
                }).then((result) => {
                    if (result.isConfirmed) {
                        localStorage.setItem('kiosk_mode', 'true');
                        window.location.href = '/kiosk';
                    }
                });
            } else {
                if(confirm("Travar máquina no Modo Totem?")) {
                    localStorage.setItem('kiosk_mode', 'true');
                    window.location.href = '/kiosk';
                }
            }
        });

        // Insere o botão antes de "Sair" e adiciona um divisor
        const items = userMenu.querySelectorAll('a');
        const sairBtn = Array.from(items).find(item => item.textContent.toLowerCase().includes('sair'));
        
        if (sairBtn) {
            const divider = document.createElement('div');
            divider.className = 'dropdown-divider';
            userMenu.insertBefore(btnTotem, sairBtn);
            userMenu.insertBefore(divider, sairBtn);
        } else {
            userMenu.appendChild(btnTotem);
        }
    }
    
    // --- Botão Voltar Flutuante para o Totem ---
    if (body.classList.contains('kiosk-mode') && window.location.pathname !== '/kiosk') {
        const btnVoltar = document.createElement('a');
        btnVoltar.href = '/kiosk';
        btnVoltar.className = 'kiosk-btn-voltar';
        btnVoltar.innerHTML = '<span class="material-icons-round">arrow_back</span> Cancelar e Voltar';
        body.appendChild(btnVoltar);
        
        // Oculta botões antigos de "Sair/Voltar" ou links pro Dashboard para não haver fugas de tela
        document.querySelectorAll('a, button, .btn').forEach(btn => {
            if (btn.classList.contains('kiosk-btn-voltar')) return;
            
            const texto = btn.textContent.toLowerCase().trim();
            const href = btn.getAttribute('href');
            
            // Se o botão se chamar exatamente "Sair" ou "Voltar", nós o escondemos
            if (texto === 'sair' || texto === 'voltar') {
                btn.style.display = 'none';
            }
            // Se for um link nativo de voltar ao painel inicial, o escondemos também
            if (href === '/' || href === '/dashboard') {
                btn.style.display = 'none';
            }
        });

        // --- Kiosk Idle Timer (Retorna ao Início e Bloqueia após 20s inativo) ---
        let idleTime = 0;
        const IDLE_LIMIT = 60; // 60 segundos

        const resetTimer = () => { idleTime = 0; };
        document.addEventListener('mousemove', resetTimer);
        document.addEventListener('keypress', resetTimer);
        document.addEventListener('touchstart', resetTimer);
        document.addEventListener('click', resetTimer);

        setInterval(() => {
            idleTime++;
            if (idleTime >= IDLE_LIMIT) {
                sessionStorage.setItem('kiosk_locked', 'true');
                window.location.href = '/kiosk'; // Volta para a tela inicial que ativará o bloqueio
            }
        }, 1000);
    }

    // --- Theme Toggler ---
    const themeBtn = document.querySelector('.theme-btn');
    const iconSun = document.querySelector('.icon-sun');
    const iconMoon = document.querySelector('.icon-moon');

    // A tema inicial é definido por um script no <head> para evitar o "flash" (FOUC).
    // Esta parte lida com o estado do botão e o evento de clique.
    if (themeBtn && iconSun && iconMoon) {
        const applyThemeVisuals = (theme) => {
            iconSun.style.display = theme === 'dark-mode' ? 'none' : 'block';
            iconMoon.style.display = theme === 'dark-mode' ? 'block' : 'none';
        };

        const saveAndApplyTheme = (theme) => {
            body.classList.remove('dark-mode', 'light-mode');
            body.classList.add(theme);
            localStorage.setItem('theme', theme);
            applyThemeVisuals(theme);
        };

        // Define o estado inicial do ícone do botão
        applyThemeVisuals(localStorage.getItem('theme') || 'light-mode');

        // Adiciona o listener de clique
        themeBtn.addEventListener('click', () => {
            const newTheme = body.classList.contains('dark-mode') ? 'light-mode' : 'dark-mode';
            saveAndApplyTheme(newTheme);
        });
    }

    // --- Responsive Header Menu (SaaS) - Corrigido ---
    const menuBtns = document.querySelectorAll('.mobile-menu-btn');
    const mainNav = document.querySelector('.main-nav');

    if (menuBtns.length > 0 && mainNav) {
        // Alternar Menu Mobile (garante que todos os botões funcionem)
        menuBtns.forEach(btn => {
            // Evita duplo disparo se o HTML tiver onclick nativo (cancela o toggle instantâneo)
            btn.removeAttribute('onclick');
            btn.addEventListener('click', (e) => {
                e.preventDefault(); // Impede recarregamento da página se o botão for um <a>
                e.stopPropagation(); // Impede fechamento fantasma
                mainNav.classList.toggle('show');
            });
        });
    }

    // --- Inteligência de Layout: Move itens do perfil e tema para dentro do Menu Mobile ---
    const moveElementsForMobile = () => {
        const headerRight = document.querySelector('.header-right');
        const topHeader = document.querySelector('.top-header');
        
        if (window.innerWidth <= 1250) {
            // Se for celular/tablet, arranca o header-right do topo e joga pro final do menu Hamburger
            if (headerRight && mainNav && headerRight.parentElement !== mainNav) {
                mainNav.appendChild(headerRight);
                headerRight.classList.add('mobile-header-right');
            }
        } else {
            // Se voltar para Desktop, devolve o header-right pro topo da página
            if (headerRight && topHeader && headerRight.parentElement !== topHeader) {
                topHeader.appendChild(headerRight);
                headerRight.classList.remove('mobile-header-right');
            }
            if (mainNav) mainNav.classList.remove('show');
        }
    };
    window.addEventListener('resize', moveElementsForMobile);
    if (mainNav) moveElementsForMobile(); // Roda na inicialização

    // Fecha dropdowns ao clicar fora
    window.addEventListener('click', (event) => {
        // Fecha o dropdown do usuário
        if (!event.target.closest('.user-dropdown')) {
            const openDropdown = document.getElementById('userMenu');
            if (openDropdown && openDropdown.classList.contains('show')) {
                openDropdown.classList.remove('show');
            }
        }
        
        // Fecha o menu principal mobile se clicar fora dele
        if (mainNav && mainNav.classList.contains('show') && !event.target.closest('.main-nav') && !event.target.closest('.mobile-menu-btn')) {
            mainNav.classList.remove('show');
        }
    });

    // Abre automaticamente o submenu se um item dentro dele estiver ativo
    document.querySelectorAll(".nav-submenu").forEach(menu => {
        if (menu.querySelector("a.active")) {
            menu.style.display = "block";
            const parentButton = menu.previousElementSibling;
            if (parentButton && parentButton.classList.contains('nav-dropdown-btn')) {
                parentButton.classList.add("open", "active-parent");
            }
        }
    });

    // Lê as mensagens flash do atributo data- no body
    const flashData = body.dataset.flashMessages;
    if (flashData && flashData !== '[]') {
        try {
            const flashMessages = JSON.parse(flashData);
            if (flashMessages.length > 0) {
                // Pega apenas a primeira e mais importante mensagem para não sobrecarregar o usuário
                const [category, message] = flashMessages[0];

                // Define o ícone e o título com base na categoria da mensagem
                let iconType = 'info';
                let titleText = 'Aviso';
                let confirmButtonColor = '#3b82f6'; // Azul padrão

                if (category === 'success') {
                    iconType = 'success';
                    titleText = 'Sucesso!';
                    confirmButtonColor = '#10b981'; // Verde
                } else if (category === 'error' || category === 'danger') {
                    iconType = 'error';
                    titleText = 'Ocorreu um Erro';
                    confirmButtonColor = '#ef4444'; // Vermelho
                } else if (category === 'warning') {
                    iconType = 'warning';
                    titleText = 'Atenção';
                    confirmButtonColor = '#f59e0b'; // Amarelo
                }

                // Lógica especial para códigos de agendamento
                const matchAg = message.match(/AG\d{4,}/i);
                if (matchAg && category === 'success') {
                    const agCode = matchAg[0].toUpperCase();
                    titleText = 'Reserva Confirmada!';
                    Swal.fire({
                        title: titleText,
                        html: `<div style="margin-bottom: 15px; font-size: 1.2rem;">${message}</div>
                               <p style="color: #94a3b8; font-size: 1.2rem; font-weight: 800; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 0;">Apresente este QR Code no leitor:</p>
                               <img src="/api/gerar_qr/${agCode}" style="width: 180px; height: 180px; border-radius: 16px; margin-top: 15px; border: 5px solid #10b981; box-shadow: 0 10px 30px rgba(16, 185, 129, 0.3);">`,
                        icon: iconType,
                        confirmButtonText: 'OK, CONTINUAR',
                        confirmButtonColor: confirmButtonColor,
                        timer: 15000,
                        timerProgressBar: true,
                        backdrop: `rgba(15, 23, 42, 0.85)`
                    }).then(() => {
                        const printIframe = document.createElement('iframe');
                        printIframe.style.position = 'fixed';
                        printIframe.style.right = '-2000px';
                        printIframe.style.bottom = '-2000px';
                        printIframe.style.width = '200px';
                        printIframe.style.height = '200px';
                        printIframe.style.border = 'none';
                        printIframe.src = `/imprimir_ticket/${agCode}`;
                        document.body.appendChild(printIframe);
                    });
                } else {
                    // Alerta Padrão para todas as outras mensagens
                    Swal.fire({
                        icon: iconType,
                        title: titleText,
                        html: message, // Permite tags HTML nas mensagens (ex: negrito, quebra de linha)
                        confirmButtonText: 'CONTINUAR',
                        confirmButtonColor: confirmButtonColor,
                        timer: 5000,
                        timerProgressBar: true,
                        backdrop: `rgba(15, 23, 42, 0.85)` // Fundo escurecido elegante
                    });
                }
            }
        } catch (e) {
            console.error("Erro ao processar mensagens flash:", e);
        }
    }

    // --- Autopreenchimento de Usuário (Evita que pessoas peguem em nome de outros) ---
    fetch('/api/current_user').then(r => r.json()).then(user => {
        if (user.logged_in) {
            const inputs = document.querySelectorAll('input[name="professor"], input[name="solicitante"], input[name="responsavel"]');
            inputs.forEach(inp => {
                if (!user.is_admin) {
                    // Usuário Comum: Preenche, trava e deixa cinza para não editar
                    inp.value = user.username;
                    inp.readOnly = true;
                    inp.style.backgroundColor = 'rgba(255, 255, 255, 0.05)';
                    inp.style.color = '#94a3b8';
                    inp.style.cursor = 'not-allowed';
                } else if (!inp.value) {
                    // Admin: Auto-preenche o nome, mas deixa livre caso queira apagar e colocar o nome de outro
                    inp.value = user.username;
                }
            });
        }
    }).catch(() => {});

    // --- MOTOR DE LEITURA IOT (Leitores USB Omnidirecionais e Gatilho) ---
    // Identifica magicamente quando os dados vêm de um leitor de código (digitação ultra-rápida)
    let scanBuffer = '';
    let scanTimer;

    document.addEventListener('keypress', function(e) {
        // Ignora se o foco estiver em um campo longo (como textarea de observações)
        if (e.target.tagName && e.target.tagName.toLowerCase() === 'textarea') return;
        
        // Se a tecla for Enter e tivermos pelo menos 2 caracteres no buffer ultrarrápido
        if (e.key === 'Enter' && scanBuffer.length >= 2) {
            // Impede que o formulário seja enviado acidentalmente pelo Enter final do leitor
            if (e.target.tagName && e.target.tagName.toLowerCase() === 'input') {
                e.preventDefault();
            }
            
            const scannedCode = scanBuffer.trim();
            scanBuffer = ''; 
            
            // Dispara evento global de sucesso de leitura
            document.dispatchEvent(new CustomEvent('scanSuccess', { detail: scannedCode }));
            return;
        }

        // Deixa o Enter normal passar se o humano estiver digitando
        if (e.key === 'Enter') return;

        scanBuffer += e.key;

        // O leitor USB digita cada letra a cada ~5-15ms. Um humano a cada ~100-200ms.
        // Se passar de 50ms sem nova tecla, consideramos digitação humana e limpamos.
        clearTimeout(scanTimer);
        scanTimer = setTimeout(() => {
            scanBuffer = '';
        }, 50);
    });

    document.addEventListener('scanSuccess', function(e) {
        const codigoCru = e.detail;
        
        // Limpeza inteligente caso o leitor capture a URL completa do QR Code do sistema
        let codigoLimpo = codigoCru.toUpperCase();
        if (codigoLimpo.includes('NOTEBOOK')) {
            codigoLimpo = codigoLimpo.replace(/;/g, '/').replace(/\\/g, '/').replace(/Ç/g, ':').split('/').pop();
        }
        // Se for um número de patrimônio puro (ex: 12), preenche com zeros (00012)
        if (!isNaN(codigoLimpo) && codigoLimpo.length < 5 && codigoLimpo.length > 0) {
            codigoLimpo = String(codigoLimpo).padStart(5, '0');
        }

        // Toca bipe digital de sucesso (Estilo Supermercado)
        try {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (AudioContext) {
                const ctx = new AudioContext();
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.frequency.value = 1500;
                gain.gain.value = 0.1;
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.start();
                gain.gain.exponentialRampToValueAtTime(0.00001, ctx.currentTime + 0.15);
                osc.stop(ctx.currentTime + 0.15);
            }
        } catch(err) {}

        // --- ROTEAMENTO AUTOMÁTICO DO CÓDIGO (Sem precisar clicar com o mouse) ---
        
        // 1. TRATAMENTO PARA CÓDIGOS DE RESERVA (Tickets AG)
        if (codigoLimpo.startsWith('AG') && codigoLimpo.length >= 6) {
            
            // 1.A Se bipou o Ticket na tela de Devolução (Carrega os itens da reserva na tela)
            if (document.getElementById('form-devolucao')) {
                fetch(`/api/reserva/${codigoLimpo}`)
                .then(r => r.json())
                .then(data => {
                    if (data.found && (data.status === 'Realizado' || data.status === 'Agendado')) {
                        if (data.itens && data.itens.length > 0) {
                            data.itens.forEach(id => {
                                if (typeof window.addItem === 'function') window.addItem(id);
                            });
                            Swal.fire({ toast: true, position: 'top-end', icon: 'success', title: `Lote da reserva carregado!`, showConfirmButton: false, timer: 2500 });
                        } else {
                            Swal.fire('Aviso', 'Esta reserva não possui equipamentos vinculados.', 'warning');
                        }
                    } else {
                        Swal.fire('Erro', 'Reserva inválida, não encontrada ou já finalizada.', 'error');
                    }
                });
                
                const manualInput = document.getElementById('manual_input');
                if (manualInput) manualInput.value = '';
            }

            // 1.A2 Se bipou o Ticket na tela de Resgatar no Sistema Normal
            else if (document.getElementById('codigo_reserva') && !document.body.classList.contains('kiosk-mode')) {
                const resgateInput = document.getElementById('codigo_reserva');
                if (resgateInput) resgateInput.value = '';
                
                if (typeof window.abrirResgateAgendamento === 'function') {
                    window.abrirResgateAgendamento(null, codigoLimpo);
                } else {
                    window.location.href = `/sessoes/efetivar_codigo/${codigoLimpo}`;
                }
            }

            // 1.B Automação do Kiosk (Abre a porta direto quando bipado na tela inicial ou no resgate)
            else if (document.body.classList.contains('kiosk-mode')) {
                const resgateInput = document.getElementById('codigo_reserva');
                if (resgateInput) resgateInput.value = '';

                window.showLoader('Validando QRCode...');
                
                // Faz a comunicação invisível e automática (Sem mudar de tela)
                fetch(`/api/iot/validar_reserva/${codigoLimpo}`)
                .then(r => r.json())
                .then(res => {
                    if(res.autorizado) {
                        if (res.tipo === 'saida') {
                            fetch('/api/iot/confirmar_saida', {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify({agendamento_id: res.agendamento_id})
                            }).then(r2 => r2.json()).then(out => {
                                window.hideLoader();
                                const slotsSaida = res.slots && res.slots.length > 0 ? res.slots.join(', ') : 'Qualquer';
                                if(out.sucesso) {
                                    Swal.fire({
                                        icon: 'success',
                                        title: 'Porta Liberada!',
                                        html: `<div style="font-size: 1.2rem; color: #cbd5e1; margin-bottom: 15px;">Saída confirmada para <b>${res.usuario}</b>.</div>
                                               <div style="background: rgba(16, 185, 129, 0.1); border: 2px solid rgba(16, 185, 129, 0.3); border-radius: 20px; padding: 20px; margin-bottom: 20px;">
                                                   <span style="color: #94a3b8; font-size: 1rem; font-weight: 800; text-transform: uppercase; letter-spacing: 2px;">Endereços para Retirar</span><br>
                                                   <div style="color: #10b981; font-size: 2.8rem; font-weight: 900; letter-spacing: 2px; margin-top: 5px; word-break: break-word; line-height: 1.1;">${slotsSaida}</div>
                                               </div>
                                               <div style="background: #ef4444; color: white; border-radius: 16px; padding: 18px; font-weight: 900; font-size: 1.4rem; letter-spacing: 1px; box-shadow: 0 10px 30px rgba(239, 68, 68, 0.4); animation: piscarVermelho 1.5s infinite; text-align: center;">
                                                   POR FAVOR, FECHE A PORTA
                                               </div>
                                               <style>@keyframes piscarVermelho { 0% { transform: scale(1); } 50% { transform: scale(1.02); } 100% { transform: scale(1); } }</style>`,
                                        showConfirmButton: true, confirmButtonText: 'JÁ FECHEI A PORTA', confirmButtonColor: '#10b981', allowOutsideClick: false, backdrop: `rgba(15, 23, 42, 0.95)`
                                    }).then((result) => { if(result.isConfirmed) { window.location.href = '/kiosk'; } });
                                } else {
                                    Swal.fire('Erro', out.mensagem, 'error');
                                }
                            });
                        } else if (res.tipo === 'devolucao') {
                            window.hideLoader();
                            Swal.fire({
                                icon: 'info',
                                title: 'Ação Correta',
                                html: 'Para devolver os equipamentos, acesse a tela de <b>"Devolução Rápida"</b> no menu e confirme os itens.',
                                confirmButtonText: 'ENTENDI',
                                confirmButtonColor: '#3b82f6'
                            });
                        }
                    } else {
                        window.hideLoader();
                        Swal.fire('Acesso Negado', res.mensagem, 'error');
                    }
                }).catch(() => {
                    window.hideLoader();
                    Swal.fire('Erro de Conexão', 'Não foi possível comunicar com o servidor IoT.', 'error');
                });
            }
            
            // 1.C Se ler o Ticket AG em outra tela, bloqueia para não fazer bagunça
            else {
                Swal.fire({ toast: true, position: 'top-end', icon: 'info', title: `Código de reserva ignorado nesta tela.`, showConfirmButton: false, timer: 2000 });
            }
            return;
        }

        // 2. TRATAMENTO PARA EQUIPAMENTOS (Patrimônios)
        
        // 2.A Tela de Devolução (Usa a função bonita que adiciona na lista visual)
        if (document.getElementById('form-devolucao') && typeof window.addItem === 'function') {
            window.addItem(codigoLimpo);
            return;
        }

        // 2.B Telas de Saída (que usam o input escondido tradicional)
        const listaIdsInput = document.querySelector('input[name="lista_ids"], #lista_ids');
        if (listaIdsInput) {
            let atuais = listaIdsInput.value.split(',').map(id => id.trim()).filter(id => id);
            if (!atuais.includes(codigoLimpo)) {
                atuais.push(codigoLimpo);
                listaIdsInput.value = atuais.join(', ');
                listaIdsInput.dispatchEvent(new Event('change'));
                Swal.fire({ toast: true, position: 'top-end', icon: 'success', title: `Item ${codigoLimpo} adicionado!`, showConfirmButton: false, timer: 1500 });
            } else {
                Swal.fire({ toast: true, position: 'top-end', icon: 'warning', title: `O Item ${codigoLimpo} já foi bipado!`, showConfirmButton: false, timer: 2000 });
            }
            return;
        }

        // 2.C Tela de Almoxarifado (Preenche o SKU e automatiza a ação)
        const inputBuscaAlmox = document.getElementById('buscaProduto') || document.getElementById('busca_produto') || document.querySelector('input[name="busca_produto"]') || document.querySelector('input[name="sku"]') || document.getElementById('sku');
        if (inputBuscaAlmox) {
            inputBuscaAlmox.value = codigoLimpo;
            inputBuscaAlmox.dispatchEvent(new Event('input')); 
            
            // Se for uma tela de Entrada/Saída, foca no campo de quantidade automaticamente
            const inputQtd = document.querySelector('input[name="quantidade"]');
            if (inputQtd) {
                inputQtd.focus();
                Swal.fire({ toast: true, position: 'top-end', icon: 'success', title: `SKU ${codigoLimpo} Lido!`, html: 'Informe a quantidade.', showConfirmButton: false, timer: 2000 });
            } else {
                // Se for a tela de listagem, pesquisa na hora sem precisar clicar no botão
                if (inputBuscaAlmox.form) inputBuscaAlmox.form.submit();
                else Swal.fire({ toast: true, position: 'top-end', icon: 'success', title: `SKU lido: ${codigoLimpo}`, showConfirmButton: false, timer: 1500 });
            }
            return;
        }

        // 2.D Segurança para Devolução Expressa via Kiosk (Modal Popup)
        if (document.body.classList.contains('kiosk-mode') && typeof Swal !== 'undefined' && Swal.isVisible()) {
            const customInput = document.getElementById('swal-input-devolucao');
            if (customInput) { customInput.value = codigoLimpo; Swal.clickConfirm(); return; }
            const swalInput = Swal.getInput();
            if (swalInput) { swalInput.value = codigoLimpo; Swal.clickConfirm(); return; }
        }

        // 2.E Telas de Busca Genérica (Inventário, Filtros, etc)
        const inputsBusca = document.querySelectorAll('input[type="search"], input[name="patrimonio"], input[name="busca"]');
        if (inputsBusca.length > 0) {
            for (let inp of inputsBusca) {
                if (inp.offsetParent !== null) { // Pega a barra de pesquisa que estiver visível
                    inp.value = codigoLimpo;
                    if (inp.form) inp.form.submit();
                    return;
                }
            }
        }
    });
});

// --- Funções Globais (necessárias para os atributos 'onclick' no HTML e outras interações) ---
window.toggleSidebar = function() {
    if (window.innerWidth <= 1250) return;

    const collapsed = document.body.classList.toggle('sidebar-collapsed');
    localStorage.setItem('sidebar_collapsed', collapsed ? 'true' : 'false');
    const button = document.querySelector('.sidebar-toggle');
    if (button) {
        button.setAttribute(
            'aria-label', collapsed ? 'Expandir menu lateral' : 'Recolher menu lateral'
        );
        button.setAttribute(
            'title', collapsed ? 'Expandir menu lateral' : 'Recolher menu lateral'
        );
    }
};

document.addEventListener('DOMContentLoaded', function() {
    if (window.innerWidth > 1250 && localStorage.getItem('sidebar_collapsed') === 'true') {
        document.body.classList.add('sidebar-collapsed');
    }
});

// Deixamos fora do DOMContentLoaded para que fiquem acessíveis globalmente.

function toggleUserMenu() {
    const menu = document.getElementById('userMenu');
    if (menu) {
        menu.classList.toggle('show');
    }
}

// Regra IDÊNTICA aplicada aos menus de navegação
window.toggleMenu = function(menuId, event) {
    if (event) {
        event.preventDefault();
        event.stopPropagation(); // Bloqueia o clique de se espalhar e fechar o menu imediatamente
    }
    
    const submenu = document.getElementById(menuId);
    if (!submenu) {
        console.error("ERRO CRÍTICO: Submenu não encontrado com o ID:", menuId);
        return;
    }
    
    const dropdownParent = submenu.closest('.nav-item-dropdown');
    
    // Fecha os outros menus do topo para eles não se sobreporem na tela
    document.querySelectorAll('.nav-submenu').forEach(m => {
        if (m.id !== menuId) {
            m.classList.remove('show');
            if (m.closest('.nav-item-dropdown')) m.closest('.nav-item-dropdown').classList.remove('menu-aberto');
        }
    });
    
    submenu.classList.toggle('show');
    if (dropdownParent) dropdownParent.classList.toggle('menu-aberto');
};

function toggleSidebarMenu(menuId, btn) {
    const menu = document.getElementById(menuId);
    if (menu) {
        if (menu.style.display === "block") {
            menu.style.display = "none";
            btn.classList.remove("open");
        } else {
            menu.style.display = "block";
            btn.classList.add("open");
        }
    }
}

// Função global de segurança para garantir a abertura do menu mobile
window.toggleMobileMenu = function(e) {
    if(e) { e.preventDefault(); e.stopPropagation(); }
    const nav = document.querySelector('.main-nav');
    if (nav) {
        nav.classList.toggle('show');
    }
};

// --- SCANNER DE CÂMERA GLOBAL ---
var scannerQrInstance = null;
var scannerTargetInput = null;
var scannerLastId = null;
var scannerLastTime = 0;

window.openScanner = function(inputId) {
    scannerTargetInput = inputId;
    const modal = document.getElementById('qrScannerModal');
    if (modal) modal.style.display = 'flex';
    
    scannerQrInstance = new Html5Qrcode("qr-reader");
    scannerQrInstance.start(
        { facingMode: "environment" }, // Força a câmera traseira (trás)
        { fps: 10, qrbox: {width: 220, height: 220}, aspectRatio: 1.0 },
        window.onScanSuccess, // Usa a função global
        function(errorMessage) { /* Ignora erros de frame do fundo */ }
    ).catch(err => {
        console.log(err);
        Swal.fire({toast: true, position: 'top-end', icon: 'error', title: 'Câmera indisponível', showConfirmButton: false, timer: 3000, customClass: { popup: 'swal2-custom-zindex' }});
        window.closeScanner();
    });
};

window.closeScanner = function() {
    const modal = document.getElementById('qrScannerModal');
    if (scannerQrInstance && scannerQrInstance.isScanning) {
        scannerQrInstance.stop().then(() => { 
            scannerQrInstance.clear(); 
            if (modal) modal.style.display = 'none'; 
        }).catch(e => { if (modal) modal.style.display = 'none'; });
    } else { 
        if (modal) modal.style.display = 'none'; 
    }
};

window.onScanSuccess = function(decodedText, decodedResult) {
    let id = decodedText.trim().toUpperCase();
    // Inteligência para extrair apenas o ID caso o QR Code contenha a URL inteira
    if (decodedText.toUpperCase().includes('/NOTEBOOK/')) id = decodedText.toUpperCase().split('/NOTEBOOK/')[1].split('/')[0].split('?')[0];
    
    const now = Date.now();
    if (id === scannerLastId && (now - scannerLastTime) < 2000) return; // Evita bipar o mesmo código 2x rápido
    scannerLastId = id; scannerLastTime = now;
    
    // --- MÁGICA: CÓDIGO DE RESERVA NA CÂMERA ---
    if (id.startsWith('AG') && id.length >= 6) {
        window.closeScanner();
        if (typeof window.abrirResgateAgendamento === 'function') {
            window.abrirResgateAgendamento(null, id.replace(/,/g, ''));
        }
        return;
    }

    const inputField = document.getElementById(scannerTargetInput);
    if (inputField) {
        // Se o campo se chamar lista_ids, permite modo metralhadora (múltiplos itens)
        let isMultiple = (inputField.name === 'lista_ids' || inputField.id.includes('lista_ids'));
        
        if (isMultiple) {
            if (inputField.value.trim() !== '') {
                let currentVals = inputField.value.split(',').map(s => s.trim());
                if(!currentVals.includes(id)){
                    inputField.value += (inputField.value.endsWith(',') ? ' ' : ', ') + id;
                    window.playBeep(); Swal.fire({toast: true, position: 'top-end', icon: 'success', title: 'Adicionado: ' + id, showConfirmButton: false, timer: 1500, customClass: { popup: 'swal2-custom-zindex' }});
                }
            } else {
                inputField.value = id;
                window.playBeep(); Swal.fire({toast: true, position: 'top-end', icon: 'success', title: 'Adicionado: ' + id, showConfirmButton: false, timer: 1500, customClass: { popup: 'swal2-custom-zindex' }});
            }
            inputField.dispatchEvent(new Event('input'));
            // MODO METRALHADORA: Não fecha a câmera! Permite bipar o próximo!
        } else {
            // Modo Único (Ex: Reportar Defeito)
            inputField.value = id;
            inputField.dispatchEvent(new Event('input'));
            window.playBeep(); Swal.fire({toast: true, position: 'top-end', icon: 'success', title: 'Lido: ' + id, showConfirmButton: false, timer: 1500, customClass: { popup: 'swal2-custom-zindex' }});
            window.closeScanner(); // Fecha a câmera automaticamente
        }
    }
};

// --- TELA INTELIGENTE DE RESGATE DE RESERVA (1-CLICK CHECKOUT) ---
window.abrirResgateAgendamento = function(e, codigoDireto = null, preloadedData = null) {
    if (e) e.preventDefault();
    if (document.getElementById('globalLoader')) document.getElementById('globalLoader').classList.remove('active');
    
    const exibirConfirmacao = (data) => {
        const isKiosk = document.body.classList.contains('kiosk-mode');
        
        // AUTOMAÇÃO CARRINHO INTELIGENTE: Se leu no Kiosk, não pergunta, abre a porta e registra direto!
        if (isKiosk && codigoDireto) {
            if (document.getElementById('globalLoader')) document.getElementById('globalLoader').classList.add('active');
            window.location.href = `/sessoes/efetivar_codigo/${data.codigo}?kiosk=1`;
            return;
        }
        const itensFormatados = data.itens && data.itens.length > 0 ? data.itens.join(', ') : 'Nenhum equipamento detalhado';
        if (window.playBeep) window.playBeep();
        
        Swal.fire({
            title: 'Confirmar Liberação',
            html: `
                <div style="text-align: left; background: rgba(0,0,0,0.2); padding: 15px; border-radius: 8px; margin-top: 10px; font-size: 0.95rem; color: #cbd5e1;">
                    <b style="color:#94a3b8;">Responsável:</b> <span style="color:#fff;">${data.solicitante}</span><br>
                    <b style="color:#94a3b8;">Destino:</b> <span style="color:#fff;">${data.finalidade}</span><br>
                    <b style="color:#94a3b8;">Devolução:</b> <span style="color:#fff;">${data.data_uso} às ${data.horario_devolucao}</span><br>
                    <hr style="border-color: rgba(255,255,255,0.1); margin: 10px 0;">
                    <b style="color: #10b981; font-size: 1.1rem;">Equipamentos Agendados:</b><br>
                    <span style="font-size: 1.1rem; font-weight: 800; color: #fff; word-break: break-word;">${itensFormatados}</span>
                </div>
            `,
            icon: 'success',
            showCancelButton: true,
            background: '#1e293b',
            color: '#ffffff',
            confirmButtonColor: '#10b981',
            cancelButtonColor: '#475569',
            confirmButtonText: 'Registrar Saída Agora',
            cancelButtonText: 'Cancelar',
            customClass: { popup: 'swal2-custom-zindex' }
        }).then((confirmResult) => {
            if (confirmResult.isConfirmed) {
                if (document.getElementById('globalLoader')) document.getElementById('globalLoader').classList.add('active');
                window.location.href = `/sessoes/efetivar_codigo/${data.codigo}`;
            }
        });
    };

    if (preloadedData) {
        exibirConfirmacao(preloadedData);
    } else if (codigoDireto) {
        fetch(`/api/reserva/${codigoDireto}`)
            .then(res => res.json())
            .then(data => {
                if (data.found) {
                    data.codigo = codigoDireto;
                    exibirConfirmacao(data);
                } else {
                    Swal.fire({icon: 'error', title: 'Inválido', text: 'Código não encontrado ou já processado.', background: '#1e293b', color: '#ffffff', customClass: { popup: 'swal2-custom-zindex' }});
                }
            });
    } else {
        Swal.fire({
            title: 'Resgatar Reserva',
            html: '<p style="color: #94a3b8; margin-bottom: 10px; font-size: 1rem;">Digite o código (Ex: AG1234)</p>',
            input: 'text',
            inputPlaceholder: 'AG...',
            icon: 'info',
            showCancelButton: true,
            background: '#1e293b',
            color: '#ffffff',
            confirmButtonColor: '#3b82f6',
            cancelButtonColor: '#ef4444',
            confirmButtonText: 'Buscar e Conferir',
            cancelButtonText: 'Cancelar',
            customClass: { input: 'swal-dark-input', popup: 'swal2-custom-zindex' },
            inputValidator: (value) => {
                if (!value) return 'Digite o código!';
            },
            showLoaderOnConfirm: true,
            preConfirm: (codigo) => {
                codigo = codigo.trim().toUpperCase();
                return fetch(`/api/reserva/${codigo}`)
                    .then(response => response.json())
                    .then(data => {
                        if (!data.found) {
                            Swal.showValidationMessage('Código inválido ou reserva já efetivada.');
                        }
                        data.codigo = codigo;
                        return data;
                    })
                    .catch(error => {
                        Swal.showValidationMessage(`Erro na busca: ${error}`);
                    });
            },
            allowOutsideClick: () => !Swal.isLoading()
        }).then((result) => {
            if (result.isConfirmed && result.value.found) {
                exibirConfirmacao(result.value);
            }
        });
    }
};

// --- FUNÇÃO IOT: DEVOLUÇÃO AVULSA SEGURA (EXIGE INTENÇÃO DO USUÁRIO) ---
window.abrirModalDevolucaoKiosk = function() {
    window.location.href = '/sessoes/devolucao?kiosk=1';
};

// --- FUNÇÃO: DESLIGAR O SISTEMA (KILL SWITCH) ---
window.confirmarDesligamento = function() {
    Swal.fire({
        title: 'Desligar o Servidor?',
        html: 'Isso irá encerrar o sistema completamente para <b>limpar a memória e o cache</b>.<br><br>Você precisará reabrir o sistema no computador principal depois.',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#ef4444',
        cancelButtonColor: '#64748b',
        confirmButtonText: 'SIM, ENCERRAR',
        cancelButtonText: 'CANCELAR',
        backdrop: `rgba(15, 23, 42, 0.9)`
    }).then((result) => {
        if (result.isConfirmed) {
            if (typeof window.showLoader === 'function') window.showLoader('Desligando Sistema...');
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = '/desligar_sistema';
            const csrfInput = document.querySelector('input[name="csrf_token"]');
            if (csrfInput) { form.appendChild(csrfInput.cloneNode()); }
            document.body.appendChild(form);
            form.submit();
        }
    });
};

// --- GLOBAL LOADER CONTROLS ---
window.showLoader = function(text = "Processando...") {
    const loader = document.getElementById('globalLoader');
    if(loader) {
        const textEl = loader.querySelector('.loader-text');
        if(textEl) textEl.innerText = text;
        loader.classList.add('active');
    }
};
window.hideLoader = function() {
    const loader = document.getElementById('globalLoader');
    if(loader) loader.classList.remove('active');
};

// --- INJEÇÃO AUTOMÁTICA: Transforma todos os ícones de QR Code do sistema em botões de câmera nativa ---
document.addEventListener('DOMContentLoaded', function() {
    const qrIcons = document.querySelectorAll('.input-with-icon .material-icons-round');
    qrIcons.forEach(icon => {
        if (icon.textContent.trim() === 'qr_code_scanner') {
            icon.style.pointerEvents = 'auto'; icon.style.cursor = 'pointer';
            icon.style.color = 'var(--primary)'; icon.style.background = 'var(--primary-light)';
            icon.style.padding = '4px'; icon.style.borderRadius = '4px'; 
            icon.title = "Clique para escanear com a Câmera";
            
            const input = icon.nextElementSibling;
            if (input && (input.tagName === 'INPUT' || input.tagName === 'TEXTAREA')) {
                if (!input.id) input.id = 'qr_input_' + Math.random().toString(36).substr(2, 9);
                icon.addEventListener('click', function() { window.openScanner(input.id); });
            }
        }
    });
    
    // INTELIGÊNCIA PARA LEITORES USB FÍSICOS (AUTOMAÇÃO TOTAL)
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && e.target.tagName === 'INPUT') {
            let input = e.target;
            let val = input.value.toUpperCase();
            
            // 1. LIMPEZA DA LEITURA (Corrige URL e teclado ABNT2)
            if (val.includes('NOTEBOOK') || val.includes('HTTPS')) {
                let itens = val.split(',');
                let itensLimpos = itens.map(item => {
                    let pedaco = item.trim();
                    if (pedaco.includes('NOTEBOOK') || pedaco.includes('HTTPS')) {
                        pedaco = pedaco.replace(/;/g, '/').replace(/\\/g, '/').replace(/Ç/g, ':');
                        let partes = pedaco.split('/');
                        let id_limpo = partes[partes.length - 1].split('?')[0];
                        if (!isNaN(id_limpo) && id_limpo.trim() !== '') {
                            return id_limpo.padStart(5, '0');
                        }
                        return id_limpo;
                    }
                    return pedaco;
                });
                input.value = itensLimpos.join(', ');
            }
            
            const idLimpo = input.value.trim().replace(/,/g, '').toUpperCase();
            if (!idLimpo) return;

            // --- MÁGICA: CÓDIGO DE RESERVA (AGXXXX) ---
            if (idLimpo.startsWith('AG')) {
                e.preventDefault();
                e.stopPropagation(); // Bloqueia a tela de dar "Erro Ativo Não Existe"
                e.stopImmediatePropagation();
                if (typeof window.abrirResgateAgendamento === 'function') {
                    window.abrirResgateAgendamento(null, idLimpo);
                }
                return;
            }

            // --- LÓGICA DE AUTOMAÇÃO ---
            e.preventDefault(); // Bloqueia o Enter de submeter o formulário

            // CENÁRIO 1: TELA DE SAÍDA (com carrinho visual)
            const saidaItemList = document.getElementById('saida-item-list');
            if (saidaItemList && input.id === 'scan_item_input') {
                const hiddenInput = document.getElementById('lista_ids');
                let currentIds = hiddenInput.value ? hiddenInput.value.split(',').map(s => s.trim()).filter(Boolean) : [];

                if (!currentIds.includes(idLimpo)) {
                    currentIds.push(idLimpo);
                    hiddenInput.value = currentIds.join(', ');

                    const itemDiv = document.createElement('div');
                    itemDiv.className = 'cart-item';
                    itemDiv.dataset.id = idLimpo;
                    itemDiv.innerHTML = `<span class="item-id">${idLimpo}</span><button type="button" class="remove-item-btn">&times;</button>`;
                    
                    itemDiv.querySelector('.remove-item-btn').addEventListener('click', function() {
                        const idToRemove = this.parentElement.dataset.id;
                        this.parentElement.remove();
                        let updatedIds = hiddenInput.value.split(',').map(s => s.trim()).filter(id => id !== idToRemove);
                        hiddenInput.value = updatedIds.join(', ');
                    });

                    saidaItemList.appendChild(itemDiv);
                    if (window.playBeep) window.playBeep();
                    Swal.fire({toast: true, position: 'top-end', icon: 'success', title: 'Adicionado: ' + idLimpo, showConfirmButton: false, timer: 1200, customClass: { popup: 'swal2-custom-zindex' }});
                } else {
                    const existingItem = saidaItemList.querySelector(`[data-id="${idLimpo}"]`);
                    if (existingItem) {
                        existingItem.classList.add('shake');
                        setTimeout(() => existingItem.classList.remove('shake'), 500);
                    }
                    Swal.fire({toast: true, position: 'top-end', icon: 'warning', title: 'Item já está na lista!', showConfirmButton: false, timer: 1200, customClass: { popup: 'swal2-custom-zindex' }});
                }
                input.value = '';
                return;
            }

            // CENÁRIO 2: TELA DE AGENDAMENTO (com botão "Adicionar")
            let btnAdd = null;
            let searchArea = input.closest('.form-group') || input.closest('.form-row') || input.form || document;
            if (searchArea) {
                btnAdd = Array.from(searchArea.querySelectorAll('button')).find(b => 
                    b.textContent.toLowerCase().includes('adicionar') || b.innerHTML.toLowerCase().includes('add') || b.classList.contains('btn-add')
                );
            }
            if (btnAdd && !btnAdd.disabled) {
                if (window.playBeep) window.playBeep();
                Swal.fire({toast: true, position: 'top-end', icon: 'success', title: 'Movido: ' + idLimpo, showConfirmButton: false, timer: 1200, customClass: { popup: 'swal2-custom-zindex' }});
                btnAdd.click();
                return;
            }

            // CENÁRIO 3: MODO METRALHADORA SIMPLES (fallback, ex: Devolução)
            let isMultiple = (input.name === 'lista_ids' || input.id.includes('lista_ids'));
            if (isMultiple) {
                if (input.value.trim() !== '' && !input.value.trim().endsWith(',')) {
                    input.value = input.value.trim() + ', ';
                }
                if (window.playBeep) window.playBeep();
                Swal.fire({toast: true, position: 'top-end', icon: 'success', title: 'Adicionado: ' + idLimpo, showConfirmButton: false, timer: 1200, customClass: { popup: 'swal2-custom-zindex' }});
            } else {
                // CENÁRIO 4: CAMPO ÚNICO (pula para o próximo)
                if (window.playBeep) window.playBeep();
                Swal.fire({toast: true, position: 'top-end', icon: 'success', title: 'Lido: ' + idLimpo, showConfirmButton: false, timer: 1200, customClass: { popup: 'swal2-custom-zindex' }});
                let form = input.form;
                if (form) {
                    let elements = Array.from(form.elements);
                    let index = elements.indexOf(input);
                    if (index > -1 && elements[index + 1]) elements[index + 1].focus();
                }
            }
        }
    }, true);

    // Carrega itens pré-existentes no carrinho visual ao carregar a página
    const initialHiddenInput = document.getElementById('lista_ids');
    const initialCart = document.getElementById('saida-item-list');
    if (initialHiddenInput && initialCart && initialHiddenInput.value) {
        const scanInput = document.getElementById('scan_item_input');
        if (scanInput) { // Check if scanInput exists
            scanInput.value = initialHiddenInput.value;
            // Simula um Enter para popular o carrinho com os dados pré-carregados
            scanInput.dispatchEvent(new KeyboardEvent('keydown', {'key': 'Enter'}));
        }
    }

    // --- GESTÃO PROFISSIONAL DE DROPDOWNS (ENGENHARIA DE SOFTWARE) ---
    document.addEventListener('click', function(e) {
        // 2. CLIQUE NO LINK (Navega para a página)
        const link = e.target.closest('.nav-submenu a');
        if (link) {
            // Ignora links que são atalhos javascript (como o de Resgatar Reserva) para não bugar a tela
            if (link.getAttribute('href') === '#') {
                document.querySelectorAll('.nav-item-dropdown').forEach(d => d.classList.remove('menu-aberto'));
                document.querySelectorAll('.nav-submenu').forEach(d => d.classList.remove('show'));
                return;
            }

            // Oculta o menu instantaneamente e mostra o Loading
            document.querySelectorAll('.nav-item-dropdown').forEach(d => d.classList.remove('menu-aberto'));
            document.querySelectorAll('.nav-submenu').forEach(d => d.classList.remove('show'));
            if (document.getElementById('globalLoader')) document.getElementById('globalLoader').classList.add('active');
            
            return;
        }

        // 3. CLIQUE FORA DO MENU
        if (!e.target.closest('.nav-item-dropdown')) {
            document.querySelectorAll('.nav-item-dropdown').forEach(d => d.classList.remove('menu-aberto'));
            document.querySelectorAll('.nav-submenu').forEach(d => d.classList.remove('show'));
        }

        // 4. LÓGICA DE FECHAMENTO: Usuário e Mobile
        const userMenu = document.getElementById('userMenu');
        const userBtn = e.target.closest('.user-btn');
        if (!userBtn && userMenu && !userMenu.contains(e.target)) {
            userMenu.classList.remove('show');
        }

        const mainNav = document.getElementById('mainNav');
        const mobileBtn = e.target.closest('.mobile-menu-btn');
        if (!mobileBtn && mainNav && !mainNav.contains(e.target) && window.innerWidth <= 992) {
            mainNav.classList.remove('show');
        }
    });

    // Evita que menus fiquem congelados se o usuário clicar no botão "Voltar" do navegador (Bfcache)
    window.addEventListener('pageshow', function() {
        document.querySelectorAll('.nav-item-dropdown').forEach(d => d.classList.remove('menu-aberto'));
        document.querySelectorAll('.nav-submenu').forEach(d => d.classList.remove('show'));
    });

    // Fechamento via Teclado ou Leitor USB
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' || e.key.length === 1 || e.key === 'Enter') {
            document.querySelectorAll('.nav-item-dropdown').forEach(d => d.classList.remove('menu-aberto'));
            document.querySelectorAll('.nav-submenu').forEach(d => d.classList.remove('show'));
        }
    });

    // --- ATIVAÇÃO DO LOADING GLOBAL AUTOMÁTICO ---
    // Ativa ao submeter formulários (exceto os que tem validação nativa que falhou)
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', function() {
            if (document.getElementById('globalLoader')) document.getElementById('globalLoader').classList.add('active');
            // Desativa após 5s por segurança (caso o download de um arquivo bloqueie a troca de página)
            setTimeout(() => { if (document.getElementById('globalLoader')) document.getElementById('globalLoader').classList.remove('active'); }, 5000);
        });
    });
    // Desativa se o usuário clicar no botão "Voltar" do navegador e a página estiver em cache
    window.addEventListener('pageshow', function(event) {
        if (event.persisted) {
            if (document.getElementById('globalLoader')) document.getElementById('globalLoader').classList.remove('active');
        }
    });

    // --- SEGURANÇA: DESATIVAR HISTÓRICO DE PREENCHIMENTO DO NAVEGADOR ---
    // Aplica autocomplete="off" em todos os formulários e inputs do sistema
    document.querySelectorAll('form, input').forEach(el => {
        el.setAttribute('autocomplete', 'off');
    });

    // --- VALIDAÇÃO EM TEMPO REAL: CADASTRO DE PATRIMÔNIO DUPLICADO ---
    if (window.location.pathname.includes('/cadastro')) {
        const inputId = document.querySelector('input[name="id"]');
        if (inputId) {
            inputId.addEventListener('blur', function() {
                let val = this.value.trim();
                if (val) {
                    fetch('/api/verificar_ativo/' + encodeURIComponent(val))
                        .then(response => response.json())
                        .then(data => {
                            if (data.exists) {
                                Swal.fire({
                                    icon: 'error',
                                    title: 'Patrimônio Duplicado!',
                                    html: `O ID <b>${data.id_limpo}</b> já está cadastrado no sistema.<br><span style="color: var(--text-muted); font-size: 0.9em;">Equipamento: ${data.modelo}</span>`,
                                    confirmButtonColor: '#ef4444',
                                    background: '#1e293b',
                                    color: '#ffffff',
                                    customClass: { popup: 'swal2-custom-zindex' }
                                });
                                this.value = ''; // Limpa o campo errado
                                setTimeout(() => this.focus(), 150); // Puxa o mouse de volta para o campo
                            }
                        });
                }
            });
        }
    }
    
    // --- INTERCEPTA CLIQUES EM "REGISTRAR SAÍDA" NO DASHBOARD PARA EXIBIR A CONFIRMAÇÃO ---
    document.addEventListener('click', function(e) {
        const checkoutLink = e.target.closest('a[href*="/sessoes/efetivar_agendamento/"]');
        if (checkoutLink) {
            e.preventDefault();
            e.stopPropagation();
            const url = checkoutLink.getAttribute('href');
            const parts = url.split('?')[0].split('/');
            const agendamentoId = parts[parts.length - 1]; // Pega o ID no final da URL
            
            if (document.getElementById('globalLoader')) document.getElementById('globalLoader').classList.add('active');
            
            fetch(`/api/reserva_by_id/${agendamentoId}`)
                .then(res => res.json())
                .then(data => {
                    if (document.getElementById('globalLoader')) document.getElementById('globalLoader').classList.remove('active');
                    if (data.found) {
                        if (typeof window.abrirResgateAgendamento === 'function') {
                            window.abrirResgateAgendamento(null, null, data);
                        }
                    } else {
                        Swal.fire({icon: 'error', title: 'Inválido', text: 'Reserva não encontrada ou já processada.', background: '#1e293b', color: '#ffffff', customClass: { popup: 'swal2-custom-zindex' }});
                    }
                })
                .catch(() => { window.location.href = url; }); // Fallback caso ocorra erro
        }
    });
});