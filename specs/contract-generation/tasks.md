# Plano de Implementação — Geração de Contratos

- [ ] 1. Preparar os modelos e a evolução do banco de dados
  - [ ] 1.1 Adicionar os campos de contrato ao modelo `Patient`
    - Incluir CPF, RG, endereço, e-mail e os três campos opcionais do responsável legal com os tipos, tamanhos e nulabilidade definidos no design.
    - Manter compatibilidade com os registros de pacientes existentes sem alterar a obrigatoriedade de nenhum campo preexistente.
    - _Requisitos: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 6.13_

  - [ ] 1.2 Criar o modelo `ProfessionalProfile` e o relacionamento com `User`
    - Criar `app/models/professional_profile.py` com os dados profissionais, timestamps e chave estrangeira única para `users.id`.
    - Configurar o relacionamento um-para-zero-ou-um nos dois modelos e exportar `ProfessionalProfile` em `app/models/__init__.py`.
    - _Requisitos: 3.1, 3.2_

  - [ ] 1.3 Adicionar os dados comerciais ao modelo `TreatmentEpisode`
    - Incluir tipo de serviço, procedimento contratado, valores, forma e condição de pagamento, quantidade de parcelas e dia de vencimento como campos opcionais.
    - Usar `Numeric(10, 2)` para valores monetários e preservar a precisão decimal.
    - Não alterar a nulabilidade nem as regras dos campos que já existem no episódio.
    - _Requisitos: 4.1, 6.13, 7.3_

  - [ ] 1.4 Implementar as migrações de runtime em `schema_updates.py`
    - Criar as rotinas idempotentes para adicionar as sete colunas de paciente e as oito colunas comerciais do episódio.
    - Criar a tabela `professional_profiles` e o índice único de `user_id` quando ausentes.
    - Registrar as três rotinas em `ensure_runtime_schema(engine)` e garantir compatibilidade com SQLite.
    - _Requisitos: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 3.1, 3.2, 4.1_

  - [ ] 1.5 Testar modelos e migrações de runtime
    - Verificar criação em banco vazio, atualização de banco legado, idempotência das rotinas e unicidade de perfil por usuário.
    - Verificar o round-trip de valores opcionais e decimais sem truncamento ou alteração silenciosa.
    - _Requisitos: 1.8, 3.2, 3.6, 4.1, 7.2; Propriedades 4 e 5_

- [ ] 2. Implementar schemas e validações de domínio
  - [ ] 2.1 Estender os schemas de paciente
    - Adicionar os sete campos opcionais a `PatientBase`, respeitando os limites de comprimento.
    - Validar CPF do paciente e do responsável legal no formato `000.000.000-00` quando preenchidos.
    - Validar o e-mail do paciente e aceitar campos opcionais vazios conforme o comportamento já adotado pelo projeto.
    - _Requisitos: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 2.8_

  - [ ] 2.2 Criar `ProfessionalProfileUpdate`
    - Validar CPF ou CNPJ com ou sem máscara, persistir somente os dígitos, e validar e-mail profissional e comprimentos máximos.
    - Remover espaços das extremidades do CREFITO e converter conteúdo vazio em `None`.
    - Preservar exatamente os demais valores válidos fornecidos.
    - _Requisitos: 3.1, 3.3, 3.4, 3.6, 3.7_

  - [ ] 2.3 Criar constantes e schema dos dados comerciais
    - Definir `SERVICE_TYPE_OPTIONS` e `PAYMENT_METHOD_OPTIONS` como fontes únicas das opções aceitas pela validação e pelos templates.
    - Criar `EpisodeContractDataUpdate` com validação de opções, valores monetários, condição à vista/parcelada, parcelas entre 2 e 60 e lista de datas ISO válidas.
    - Aplicar ao valor de sessão preenchido o intervalo exigido pelo formulário, de `0.01` a `999999.99`.
    - _Requisitos: 4.1, 4.2, 4.7, 4.8, 4.9, 7.6, 7.7_

  - [ ] 2.4 Criar testes baseados em propriedades para as validações
    - Usar Hypothesis com no mínimo 100 exemplos por propriedade e identificar cada teste com o comentário definido no design.
    - Cobrir rejeição de CPF/CNPJ inválido, rejeição de e-mail inválido, normalização de CREFITO e rejeição de valores de domínio inválidos.
    - Confirmar que uma falha de validação impede qualquer escrita no banco nos testes de integração correspondentes.
    - _Requisitos: 1.5, 1.6, 2.4, 3.3, 3.4, 3.7, 4.2, 4.7, 4.8, 4.9, 7.6, 7.7; Propriedades 1, 2, 6 e 7_

- [ ] 3. Integrar os novos dados ao cadastro de pacientes
  - [ ] 3.1 Atualizar o formulário de criação e edição de paciente
    - Adicionar as seções de documentos/contato e responsável legal com valores pré-preenchidos na edição.
    - Exibir erros por campo sem apagar os dados submetidos.
    - Marcar visualmente o CPF ausente quando houver nome de responsável legal e permitir o salvamento com aviso; não exigir vínculo.
    - _Requisitos: 1.5, 1.6, 1.8, 2.5, 2.6, 2.7, 2.8_

  - [ ] 3.2 Atualizar as rotas de criação e edição de paciente
    - Receber e validar os novos campos de forma atômica antes de persistir.
    - Rejeitar CPF duplicado, desconsiderando o próprio registro durante a edição, e devolver mensagem em português com status 422.
    - Preservar todos os campos submetidos ao reexibir o formulário após erro.
    - _Requisitos: 1.5, 1.6, 1.7, 1.8, 2.4, 2.5, 2.6, 2.8_

  - [ ] 3.3 Testar o fluxo cadastral de paciente
    - Cobrir criação e edição válidas, campos em branco, formatos inválidos, CPF duplicado e os cenários do responsável legal.
    - Criar teste de propriedade para garantir unicidade de CPF não nulo e round-trip dos dados cadastrais.
    - _Requisitos: 1.5, 1.6, 1.7, 1.8, 2.4, 2.5, 2.6, 2.7, 2.8; Propriedades 3 e 4_

- [ ] 4. Implementar a área de perfil profissional
  - [ ] 4.1 Criar as rotas GET e POST de `/profile`
    - Carregar o perfil do usuário autenticado ou apresentar um objeto vazio no GET.
    - Validar toda a submissão antes de fazer upsert, garantindo no máximo um perfil por usuário.
    - Em erro de validação ou persistência, fazer rollback, manter os valores informados e reexibir o formulário sem redirecionar.
    - Após sucesso, redirecionar para `/profile` com status 303 e confirmação.
    - _Requisitos: 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8_

  - [ ] 4.2 Criar o template de perfil e o acesso pela navegação
    - Criar `templates/profile/form.html` com os quatro campos, valores atuais, erros e mensagem de sucesso.
    - Aplicar máscara dinâmica de CPF/CNPJ no navegador sem incluir os caracteres da máscara no valor persistido.
    - Adicionar o link “Meu perfil” em `templates/base.html` para usuários autenticados.
    - Registrar o router de perfil em `main.py`.
    - _Requisitos: 3.5, 3.6, 3.8_

  - [ ] 4.3 Testar o fluxo de perfil profissional
    - Cobrir perfil inicialmente vazio, criação, atualização idempotente, validações, normalização do CREFITO e falha simulada de banco com preservação do formulário.
    - Criar teste de propriedade para o upsert e o round-trip dos campos válidos.
    - _Requisitos: 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8; Propriedades 4, 5 e 6_

- [ ] 5. Implementar a edição dos dados comerciais do episódio
  - [ ] 5.1 Criar as rotas GET e POST de dados do contrato
    - Criar o router de episódios com os endpoints `/treatment-episodes/{episode_id}/contract-data`.
    - Carregar o episódio existente, validar os oito campos comerciais de forma atômica e redirecionar para o detalhe do paciente após sucesso.
    - Aceitar todos os dados comerciais em branco e impedir alterações quando a cirurgia estiver com status “Alta”, inclusive contra submissão POST direta.
    - Registrar o router em `main.py`.
    - _Requisitos: 4.1, 4.2, 4.7, 4.8, 4.9, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_

  - [ ] 5.2 Criar o formulário de dados comerciais
    - Criar `templates/episodes/contract_data_form.html` com as opções definidas nos schemas e valores persistidos pré-preenchidos.
    - Exibir asterisco e estado de erro no valor correspondente a “Avulso” ou “Pacote” quando estiver ausente, sem transformar a ausência em bloqueio de persistência.
    - Para “Parcelado”, gerar as datas mensais a partir do primeiro vencimento e permitir edição individual; para “À vista”, ocultar e persistir quantidade/cronograma como nulos.
    - Desabilitar visualmente todos os campos quando o episódio estiver associado a uma cirurgia com status “Alta”.
    - Preservar os valores submetidos e mostrar mensagens em português após validação inválida.
    - _Requisitos: 4.3, 4.4, 7.1, 7.2, 7.3, 7.5, 7.6, 7.7_

  - [ ] 5.3 Integrar o acesso aos dados comerciais no detalhe do paciente
    - Adicionar “Dados do contrato” a cada episódio e direcionar ao formulário do episódio correto.
    - Manter o comportamento e os controles existentes do bloco do episódio.
    - _Requisitos: 7.1, 7.2, 7.4, 7.5_

  - [ ] 5.4 Testar formulário, autorização de edição e persistência comercial
    - Cobrir campos vazios, opções inválidas, limites monetários, vencimento, texto acima de 1000 caracteres, pré-preenchimento e bloqueio de episódio com alta.
    - Criar testes de propriedade para rejeição de domínio e round-trip de combinações válidas e nulas.
    - _Requisitos: 4.1, 4.2, 4.3, 4.4, 4.7, 4.8, 4.9, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7; Propriedades 4 e 7_

- [ ] 6. Checkpoint — Validar cadastros e dados comerciais
  - Executar a suíte implementada até este ponto e corrigir falhas antes de iniciar a geração do documento.
  - Confirmar manualmente que bancos existentes são atualizados sem perda de dados e que os três formulários mantêm os valores após erro.

- [ ] 7. Implementar o gerador de contrato em PDF
  - [ ] 7.1 Implementar a validação de completude do contrato
    - Criar `app/contract_validation.py` com `get_missing_contract_fields`, sem adicionar validações de obrigatoriedade aos modelos ou schemas de cadastro.
    - Verificar CPF, RG, endereço e e-mail do paciente; perfil profissional; tipo de serviço, procedimento, forma e condição de pagamento; valor condicional; e cronograma completo quando parcelado.
    - Quando houver nome de responsável legal, verificar também CPF e vínculo/parentesco; quando não houver nome, não exigir nenhum dado do responsável.
    - Tratar `None`, texto vazio e texto somente com espaços como ausentes e retornar todas as pendências agrupadas, com rótulos legíveis, em uma única execução.
    - _Requisitos: 2.5, 2.6, 2.8, 4.5, 4.6, 6.8, 6.12, 6.13_

  - [ ] 7.2 Criar helpers e estrutura base de `app/contract_pdf.py`
    - Implementar `_slug` com normalização Unicode e estilos reutilizáveis do ReportLab.
    - Fazer o módulo receber objetos ORM e devolver um `BytesIO` posicionado para leitura, sem depender de request ou response.
    - Assumir dados previamente validados, sem produzir placeholders nem PDFs parciais para dados incompletos.
    - Tratar a ausência do ReportLab com a mensagem definida no design.
    - _Requisitos: 6.3, 6.4, 6.8, 6.12_

  - [ ] 7.3 Compor identificação, objeto, condições comerciais e cláusulas fixas
    - Renderizar CONTRATADO, CONTRATANTE e, condicionalmente, RESPONSÁVEL LEGAL com os dados que passaram pela validação de completude.
    - Renderizar o procedimento/plano terapêutico, tipo de serviço, valores, forma e condição de pagamento e, quando parcelado, todas as datas de vencimento.
    - Incluir local, data e linhas de assinatura, cuidando da paginação e evitando cortes de blocos.
    - _Requisitos: 6.5, 6.6, 6.8, 6.12_

  - [ ] 7.4 Implementar a seção estática de consentimento de imagem
    - Incluir sempre a cláusula de LGPD após as demais cláusulas, sem criar campos de consentimento no banco.
    - Renderizar AUTORIZO/NÃO AUTORIZO, todos os meios, finalidades e opções de identificação especificados, além da assinatura própria do paciente ou responsável.
    - Usar checkboxes imprimíveis e espaço suficiente para preenchimento manual.
    - _Requisitos: 5.1, 5.2, 5.3, 5.4, 6.7_

  - [ ] 7.5 Criar testes unitários e baseados em propriedades da validação e do PDF
    - Testar a lista completa e agrupada de pendências para dados `None`, vazios e compostos somente por espaços, incluindo valores condicionais e responsável legal.
    - Extrair texto de PDFs gerados com dados completos para verificar as seções obrigatórias e o consentimento sempre presente.
    - Cobrir inclusão e omissão condicional do responsável legal.
    - Testar `_slug` com acentos, cedilha, espaços repetidos, caracteres especiais e texto Unicode arbitrário.
    - Identificar e executar com Hypothesis as propriedades 8, 9, 10 e 11 com no mínimo 100 exemplos quando aplicável, confirmando que a ausência de dados não altera sua opcionalidade na persistência.
    - _Requisitos: 4.5, 4.6, 5.1, 5.2, 5.3, 5.4, 6.3, 6.5, 6.6, 6.7, 6.8, 6.12, 6.13; Propriedades 8, 9, 10 e 11_

- [ ] 8. Disponibilizar o download do contrato
  - [ ] 8.1 Criar o endpoint de contrato no router de pacientes
    - Implementar `GET /patients/{patient_id}/treatment-episodes/{episode_id}/contract.pdf` para usuário autenticado.
    - Verificar a existência do paciente e se o episódio pertence a ele antes de gerar qualquer conteúdo.
    - Buscar o perfil profissional e executar a validação de completude antes de chamar o gerador.
    - Se houver pendências, não chamar `generate_contract_pdf`; reexibir o detalhe do paciente com status 422, o motivo da não geração e a lista completa agrupada por seção.
    - Se os dados estiverem completos, gerar o PDF e devolvê-lo em `StreamingResponse` com `application/pdf` e nome `contrato_{slug}_{episode_id}.pdf`.
    - Registrar exceções inesperadas no log, sem expor detalhes internos, e responder com a mensagem de falha definida no design.
    - _Requisitos: 4.5, 4.6, 6.2, 6.3, 6.4, 6.8, 6.9, 6.10, 6.11, 6.12_

  - [ ] 8.2 Adicionar o botão “Gerar contrato” ao detalhe do paciente
    - Posicionar o botão em cada episódio, ao lado de “Baixar evolução”, apontando para o paciente e o episódio corretos.
    - Manter o botão disponível mesmo com dados incompletos; após o clique, exibir uma mensagem clara e todos os campos pendentes do episódio correspondente, com acessos para edição.
    - _Requisitos: 6.1, 6.8, 6.12_

  - [ ] 8.3 Testar o endpoint e sua integração com a interface
    - Verificar status, tipo de conteúdo, cabeçalho de download, nome normalizado, PDF válido e presença do botão no episódio correto.
    - Cobrir episódio inexistente, paciente inexistente, episódio de outro paciente, perfil ausente/incompleto, dados do paciente e comerciais incompletos e falha simulada do gerador.
    - Confirmar por mock que o gerador não é chamado quando houver qualquer pendência e que todos os campos ausentes aparecem na resposta.
    - Criar o teste de propriedade de isolamento de episódios por paciente.
    - _Requisitos: 4.5, 4.6, 6.1, 6.3, 6.8, 6.9, 6.10, 6.12, 6.13; Propriedades 9, 11 e 12_

- [ ] 9. Executar validação final da funcionalidade
  - [ ] 9.1 Executar a suíte completa e revisar regressões
    - Executar testes unitários, de propriedade e de integração, incluindo fluxos existentes de pacientes, episódios, atendimentos e relatório de evolução.
    - Confirmar que todos os routers, modelos e templates novos são carregados na inicialização da aplicação.
    - _Requisitos: 1.1–1.8, 2.1–2.8, 3.1–3.8, 4.1–4.9, 5.1–5.4, 6.1–6.13, 7.1–7.7_

  - [ ] 9.2 Realizar verificações manuais do PDF e de desempenho
    - Inspecionar visualmente contratos com dados completos, responsável legal e conteúdo longo, verificando paginação, acentuação, checkboxes e assinaturas.
    - Tentar gerar com diferentes combinações de dados incompletos e confirmar que nenhum arquivo é produzido e que a mensagem lista todas as pendências.
    - Medir a geração com episódios de até 50 atendimentos e com mais de 50, confirmando respectivamente os limites de 10 e 30 segundos.
    - Confirmar que nenhuma informação de consentimento de imagem é persistida no banco.
    - _Requisitos: 5.1, 5.2, 5.3, 5.4, 6.2, 6.5, 6.7, 6.8, 6.11, 6.12, 6.13_

- [ ] 10. Checkpoint final — Confirmar aceite da especificação
  - Verificar que todos os critérios dos requisitos estão cobertos por implementação, teste automatizado ou verificação manual explicitamente indicada.
  - Confirmar que as 12 propriedades de correção possuem testes identificados conforme o padrão do design e que toda a suíte passa.
