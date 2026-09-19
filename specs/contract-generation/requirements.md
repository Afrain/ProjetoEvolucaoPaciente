# Requirements Document

## Introduction

Esta funcionalidade adiciona a geração de contratos de prestação de serviços de fisioterapia em PDF ao sistema FisioGestao. O contrato é vinculado a um ciclo de tratamento (TreatmentEpisode) e reúne dados do paciente (CONTRATANTE), do fisioterapeuta responsável (CONTRATADO) e das condições comerciais do serviço. O PDF inclui, ao final, a seção de autorização de uso de imagem (LGPD) como formulário estático para preenchimento manual pelo paciente no momento da assinatura — nenhum dado de consentimento é armazenado no banco. Para viabilizar a geração, novos campos opcionais precisam ser adicionados ao cadastro do paciente, ao perfil profissional do fisioterapeuta e ao próprio episódio de tratamento. Nenhum campo já existente terá sua obrigatoriedade alterada e os novos campos poderão ser salvos em branco; a completude será exigida somente no momento da geração do contrato.

---

## Glossary

- **Sistema**: o FisioGestao como um todo.
- **Gerador_de_Contrato**: módulo responsável por compor e renderizar o PDF do contrato.
- **Contrato**: documento PDF de prestação de serviços de fisioterapia gerado pelo Gerador_de_Contrato.
- **Paciente**: entidade `Patient` — o CONTRATANTE no contrato.
- **Fisioterapeuta**: entidade `User` autenticado que atende o paciente — o CONTRATADO no contrato.
- **Perfil_Profissional**: entidade que estende os dados do Fisioterapeuta com informações profissionais e fiscais necessárias ao contrato.
- **Episódio**: entidade `TreatmentEpisode` — unidade de ciclo de tratamento à qual o contrato é vinculado.
- **Dados_Comerciais**: conjunto de campos financeiros e de serviço associados a um Episódio.
- **Responsável_Legal**: pessoa responsável pelo Paciente quando este é menor de idade ou incapaz de assinar por si.
- **CREFITO**: número de registro do fisioterapeuta no Conselho Regional de Fisioterapia e Terapia Ocupacional.
- **CPF**: Cadastro de Pessoa Física — documento de identificação fiscal brasileiro.
- **RG**: Registro Geral — documento de identidade civil brasileiro.
- **LGPD**: Lei Geral de Proteção de Dados (Lei nº 13.709/2018).
- **ReportLab**: biblioteca Python usada para geração de PDFs, já presente no projeto.
- **Parcelas**: conjunto de datas de vencimento individuais, uma por parcela, associadas a um Episódio quando a condição de pagamento é "Parcelado".
- **Dia_Base_Vencimento**: dia do mês informado pelo fisioterapeuta usado para calcular automaticamente as datas de vencimento das Parcelas.

---

## Requirements

### Requisito 1: Campos de identificação do Paciente

**História de usuário:** Como fisioterapeuta, quero registrar CPF, RG, endereço e e-mail do paciente, para que essas informações constem no contrato de prestação de serviços.

#### Critérios de Aceitação

1. THE Sistema SHALL armazenar o CPF do Paciente como texto de até 14 caracteres no formato `000.000.000-00`, permitindo valor nulo.
2. THE Sistema SHALL armazenar o RG do Paciente como texto de até 20 caracteres, permitindo valor nulo.
3. THE Sistema SHALL armazenar o endereço completo do Paciente (`address`) como texto de até 300 caracteres, permitindo valor nulo.
4. THE Sistema SHALL armazenar o e-mail do Paciente como texto de até 120 caracteres, permitindo valor nulo.
5. IF o usuário submete o formulário de cadastro ou edição do Paciente com um CPF preenchido que não corresponda ao padrão de 11 dígitos numéricos no formato `000.000.000-00`, THEN THE Sistema SHALL exibir uma mensagem de erro indicando formato de CPF inválido e não persistir nenhum dado do formulário.
6. IF o usuário submete o formulário de cadastro ou edição do Paciente com um e-mail preenchido que não contenha exatamente um caractere `@` seguido de pelo menos um caractere e um `.` com pelo menos um caractere após o `.`, THEN THE Sistema SHALL exibir uma mensagem de erro indicando e-mail inválido e não persistir nenhum dado do formulário.
7. IF o usuário submete o formulário de cadastro ou edição do Paciente com um CPF preenchido que já esteja associado a outro Paciente cadastrado, THEN THE Sistema SHALL exibir uma mensagem de erro indicando CPF duplicado e não persistir os dados.
8. WHEN o usuário salva o cadastro do Paciente com CPF, RG, endereço e e-mail todos válidos ou em branco, THE Sistema SHALL persistir exatamente os valores fornecidos, sem modificação ou truncamento, e retornar confirmação de sucesso ao usuário.

---

### Requisito 2: Responsável Legal do Paciente (opcional)

**História de usuário:** Como fisioterapeuta, quero registrar os dados do responsável legal do paciente quando ele for menor de idade ou incapaz, para que o contrato identifique corretamente o signatário.

#### Critérios de Aceitação

1. THE Sistema SHALL armazenar o nome do Responsável_Legal (`legal_guardian_name`) como texto de até 140 caracteres, permitindo valor nulo.
2. THE Sistema SHALL armazenar o CPF do Responsável_Legal (`legal_guardian_cpf`) como texto de até 14 caracteres, permitindo valor nulo.
3. THE Sistema SHALL armazenar o grau de parentesco ou vínculo do Responsável_Legal (`legal_guardian_relationship`) como texto de até 60 caracteres (ex.: "mãe", "pai", "curador"), permitindo valor nulo.
4. IF o usuário submete o formulário com `legal_guardian_cpf` preenchido em formato diferente de 11 dígitos numéricos no padrão `000.000.000-00`, THEN THE Sistema SHALL exibir mensagem de erro indicando CPF do responsável legal inválido e não persistir nenhum dado do formulário.
5. WHEN o usuário submete o formulário com `legal_guardian_name` em branco, THE Sistema SHALL aceitar o salvamento independentemente do estado de `legal_guardian_cpf` e `legal_guardian_relationship`.
6. WHEN o usuário submete o formulário com `legal_guardian_name` preenchido e `legal_guardian_cpf` em branco, THE Sistema SHALL exibir aviso indicando ausência do CPF do responsável legal e permitir o salvamento prosseguir.
7. WHEN o formulário exibe `legal_guardian_name` preenchido e `legal_guardian_cpf` em branco, THE Sistema SHALL indicar visualmente no campo `legal_guardian_cpf` que o dado está ausente.
8. WHEN o usuário submete o formulário com `legal_guardian_name` preenchido e `legal_guardian_relationship` em branco, THE Sistema SHALL aceitar o salvamento normalmente sem exibir erro ou aviso sobre o campo `legal_guardian_relationship`.

---

### Requisito 3: Perfil Profissional do Fisioterapeuta

**História de usuário:** Como fisioterapeuta, quero registrar meu CPF/CNPJ, número do CREFITO, endereço profissional e e-mail profissional no sistema, para que esses dados apareçam corretamente no contrato como CONTRATADO.

#### Critérios de Aceitação

1. THE Sistema SHALL manter uma entidade Perfil_Profissional com os campos: `cpf_cnpj` (texto, até 14 dígitos numéricos, sem máscara), `crefito` (texto, até 30 caracteres), `professional_address` (texto, até 300 caracteres) e `professional_email` (texto, até 120 caracteres), todos opcionais.
2. THE Sistema SHALL associar exatamente um Perfil_Profissional a cada Fisioterapeuta (User), com relação de um para um.
3. WHEN o Fisioterapeuta salva o Perfil_Profissional com `cpf_cnpj` preenchido em formato inválido (nem `000.000.000-00` nem `00.000.000/0000-00`), THEN THE Sistema SHALL exibir mensagem de erro indicando CPF/CNPJ inválido e não persistir nenhum campo do formulário no banco de dados.
4. WHEN o Fisioterapeuta salva o Perfil_Profissional com `professional_email` preenchido em formato inválido (ausência de `@` ou ausência de domínio com pelo menos um ponto após o `@`), THEN THE Sistema SHALL exibir mensagem de erro indicando e-mail profissional inválido e não persistir nenhum campo do formulário no banco de dados.
5. WHEN o Fisioterapeuta acessa a área de perfil profissional, THE Sistema SHALL exibir um formulário com os quatro campos da entidade Perfil_Profissional pré-preenchidos com os valores atualmente persistidos, ou em branco caso nenhum valor tenha sido salvo anteriormente.
6. WHEN o Fisioterapeuta salva o Perfil_Profissional com todos os campos válidos ou em branco, THE Sistema SHALL persistir exatamente os valores fornecidos sem modificação e redirecionar o Fisioterapeuta para a área de perfil profissional exibindo os valores recém-salvos.
7. IF o Fisioterapeuta salva o Perfil_Profissional com `crefito` contendo apenas espaços ou com comprimento zero após remoção de espaços nas extremidades, THEN THE Sistema SHALL tratar o campo como em branco e persistir o valor vazio sem exibir erro.
8. IF ocorrer falha de persistência ao salvar o Perfil_Profissional por indisponibilidade do banco de dados, THEN THE Sistema SHALL exibir mensagem de erro indicando falha ao salvar e preservar os valores inseridos no formulário sem redirecionamento.
9. WHEN o Fisioterapeuta digita o CPF/CNPJ no Perfil_Profissional, THE Sistema SHALL aplicar visualmente a máscara de CPF ou CNPJ conforme a quantidade de dígitos, mas SHALL remover pontos, traço e barra antes de persistir, armazenando somente os 11 dígitos do CPF ou os 14 dígitos do CNPJ.

---

### Requisito 4: Dados Comerciais do Episódio

**História de usuário:** Como fisioterapeuta, quero registrar tipo de serviço, valores, forma e condição de pagamento e, quando parcelado, quantidade de parcelas e vencimento, para que essas informações constem no contrato vinculado ao episódio.

#### Critérios de Aceitação

1. THE Sistema SHALL armazenar os seguintes Dados_Comerciais associados a cada Episódio:
   - `service_type`: texto de até 30 caracteres, com as opções "Avulso", "Pacote" e "Outro".
   - `contracted_procedure`: texto livre de até 1000 caracteres descrevendo o procedimento e plano terapêutico inicial.
   - `session_value`: valor decimal não negativo com até 10 dígitos no total e 2 casas decimais, permitindo valor nulo.
   - `package_value`: valor decimal não negativo com até 10 dígitos no total e 2 casas decimais, permitindo valor nulo.
   - `payment_method`: texto de até 40 caracteres, com as opções "Dinheiro", "Pix", "Cartão de débito", "Cartão de crédito", "Transferência bancária" e "Outro".
   - `payment_condition`: texto de até 20 caracteres, com as opções "À vista" e "Parcelado", permitindo valor nulo.
   - `installment_count`: quantidade de parcelas, inteiro entre 2 e 60, permitindo valor nulo.
   - `installment_due_dates`: lista de datas de vencimento, uma por parcela (tipo: JSON ou texto serializado, armazenado como TEXT), permitindo valor nulo. Cada data individual deve ser uma data válida no formato `YYYY-MM-DD`. A quantidade de datas deve ser igual a `installment_count` quando `payment_condition` é "Parcelado".
2. IF o usuário submete os Dados_Comerciais com `session_value` ou `package_value` negativo, THEN THE Sistema SHALL exibir mensagem de erro indicando valor inválido e não persistir.
3. WHEN `service_type` é "Avulso" e o usuário submete o formulário, THE Sistema SHALL exibir asterisco no rótulo do campo `session_value` e borda vermelha no campo caso esteja em branco.
4. WHEN `service_type` é "Pacote" e o usuário submete o formulário, THE Sistema SHALL exibir asterisco no rótulo do campo `package_value` e borda vermelha no campo caso esteja em branco.
5. IF o usuário tenta gerar o contrato com `service_type` igual a "Avulso" e `session_value` em branco, THEN THE Sistema SHALL impedir a geração e informar que o campo "Valor da sessão" precisa ser preenchido.
6. IF o usuário tenta gerar o contrato com `service_type` igual a "Pacote" e `package_value` em branco, THEN THE Sistema SHALL impedir a geração e informar que o campo "Valor do pacote" precisa ser preenchido.
7. IF o usuário seleciona um `service_type` fora das opções permitidas, THEN THE Sistema SHALL exibir mensagem de erro indicando seleção inválida e não persistir.
8. IF o usuário seleciona um `payment_method` fora das opções permitidas, THEN THE Sistema SHALL exibir mensagem de erro indicando seleção inválida e não persistir.
9. IF o usuário seleciona `payment_condition` fora das opções "À vista" e "Parcelado", THEN THE Sistema SHALL exibir mensagem de erro indicando condição inválida e não persistir.
10. IF o usuário informa `installment_count` fora do intervalo de 2 a 60, THEN THE Sistema SHALL exibir mensagem de erro indicando a quantidade válida e não persistir.
11. WHEN `payment_condition` é "À vista", THE Sistema SHALL ocultar a quantidade e o cronograma de parcelas e persistir ambos como nulos.
12. WHEN `payment_condition` é "Parcelado" e o usuário informa a quantidade de parcelas e a primeira data de vencimento, THE Sistema SHALL preencher automaticamente uma data para cada mês subsequente, preservando o dia sempre que ele existir no mês e usando o último dia nos meses menores.
13. WHEN as datas forem geradas automaticamente, THE Sistema SHALL permitir que o usuário altere individualmente qualquer vencimento antes de salvar.
14. IF `payment_condition` é "Parcelado" e a quantidade de datas válidas for diferente de `installment_count`, THEN THE Sistema SHALL impedir a geração do contrato e informar que o cronograma de vencimentos precisa ser completado.

---

### Requisito 5: Seção de Consentimento de Imagem no Contrato (LGPD)

**História de usuário:** Como fisioterapeuta, quero que o contrato gerado em PDF inclua a seção de autorização de uso de imagem completa e pronta para preenchimento manual, para que o paciente possa marcá-la à mão no momento da assinatura do contrato.

#### Critérios de Aceitação

1. THE Gerador_de_Contrato SHALL incluir no PDF, após as demais cláusulas, a seção completa de autorização de uso de imagem conforme o modelo de contrato, com todos os campos de checkbox e linha de assinatura para preenchimento manual pelo Paciente.
2. THE Gerador_de_Contrato SHALL incluir na seção os seguintes blocos para preenchimento manual:
   - opção de AUTORIZO / NÃO AUTORIZO (checkboxes impressos)
   - checkboxes de meios autorizados: Instagram, Facebook, TikTok, Site profissional, WhatsApp profissional, Materiais institucionais, Palestras e apresentações, Outros
   - checkboxes de finalidades autorizadas: Divulgação profissional, Conteúdo educativo, Demonstração de evolução, Comparação antes/depois, Depoimento do paciente, Finalidade acadêmica/científica, Outras
   - opções de identificação: Autorizo primeiro nome / Autorizo identificação completa / NÃO autorizo identificação
   - linha para assinatura específica do Paciente/Responsável Legal
3. THE Gerador_de_Contrato SHALL sempre incluir esta seção no PDF, independentemente de qualquer configuração do episódio ou do paciente — a decisão de autorizar ou não é feita pelo paciente no papel.
4. THE Sistema SHALL armazenar zero campos adicionais no banco de dados relacionados ao consentimento de imagem — toda a lógica desta seção é exclusivamente de renderização no PDF.

---

### Requisito 6: Geração do PDF do Contrato

**História de usuário:** Como fisioterapeuta, quero gerar o contrato em PDF a partir da tela de detalhes do ciclo de tratamento, para que eu possa imprimir ou enviar ao paciente de forma rápida.

#### Critérios de Aceitação

1. THE Sistema SHALL exibir o botão "Gerar contrato" dentro do bloco de cada Episódio na tela de detalhes do Paciente (`/patients/{id}`), posicionado ao lado do botão "Baixar evolução".
2. WHEN o usuário clica em "Gerar contrato", os dados necessários estão completos e o Episódio possui até 50 atendimentos registrados, THE Gerador_de_Contrato SHALL responder com o arquivo PDF dentro de 10 segundos.
3. THE Gerador_de_Contrato SHALL nomear o arquivo PDF no formato `contrato_{nome_paciente_slug}_{id_episodio}.pdf`, onde `nome_paciente_slug` é o nome completo do paciente em letras minúsculas com espaços substituídos por underscores e caracteres especiais removidos.
4. THE Gerador_de_Contrato SHALL utilizar a biblioteca ReportLab para renderização do PDF.
5. THE Gerador_de_Contrato SHALL compor o PDF com as seguintes seções na ordem indicada: identificação das partes, objeto do contrato, condições comerciais, obrigações do CONTRATADO, obrigações do CONTRATANTE, vigência e rescisão e, quando aplicável, autorização de uso de imagem.
6. WHEN `legal_guardian_name` do Paciente estiver preenchido e a validação de completude for satisfeita, THE Gerador_de_Contrato SHALL incluir a seção de Responsável_Legal no bloco de identificação do CONTRATANTE, exibindo nome completo, CPF e grau de parentesco ou vínculo.
7. THE Gerador_de_Contrato SHALL sempre incluir a seção de autorização de uso de imagem no PDF como formulário estático para preenchimento manual pelo Paciente, sem dependência de dados do banco.
8. WHEN o usuário clica em "Gerar contrato" e qualquer dado necessário estiver ausente, THE Sistema SHALL impedir a geração do PDF e exibir a mensagem "Não foi possível gerar o contrato. Preencha os campos obrigatórios para o contrato:" seguida da lista completa de campos ausentes, agrupada em "Paciente", "Perfil profissional", "Dados comerciais" e, quando aplicável, "Responsável legal".
9. IF ocorrer erro interno durante a geração do PDF, THEN THE Gerador_de_Contrato SHALL retornar mensagem de erro indicando falha na geração do contrato e registrar o erro no log da aplicação.
10. IF o Episódio informado não existir ou não pertencer ao Paciente identificado na URL, THEN THE Gerador_de_Contrato SHALL retornar mensagem de erro indicando recurso não encontrado sem gerar arquivo PDF.
11. WHEN o usuário clica em "Gerar contrato", os dados necessários estão completos e o Episódio possui mais de 50 atendimentos registrados, THE Gerador_de_Contrato SHALL responder com o arquivo PDF dentro de 30 segundos.
12. THE Sistema SHALL considerar necessários exclusivamente para a geração do contrato: `cpf`, `rg`, `address` e `email` do Paciente; `cpf_cnpj`, `crefito`, `professional_address` e `professional_email` do Perfil_Profissional; `service_type`, `contracted_procedure`, `payment_method` e `payment_condition` do Episódio; `session_value` quando o serviço for "Avulso"; `package_value` quando o serviço for "Pacote"; `installment_count` e um item válido em `installment_due_dates` para cada parcela quando a condição for "Parcelado"; e, se `legal_guardian_name` estiver preenchido, `legal_guardian_cpf` e `legal_guardian_relationship`.
13. THE Sistema SHALL manter inalterada a obrigatoriedade dos campos que já existiam antes desta funcionalidade e SHALL manter todos os campos adicionados por esta funcionalidade opcionais no banco de dados e nos formulários de cadastro e edição.

---

### Requisito 7: Formulário de Dados Comerciais do Episódio

**História de usuário:** Como fisioterapeuta, quero preencher os dados comerciais diretamente na criação ou edição do ciclo de tratamento, para que o contrato seja gerado sem etapas adicionais.

#### Critérios de Aceitação

1. THE Sistema SHALL exibir os campos de Dados_Comerciais no mesmo formulário de criação e edição do Episódio.
2. WHEN o usuário abre o formulário de edição de um Episódio existente, THE Sistema SHALL pré-preencher todos os campos de Dados_Comerciais com os valores persistidos para aquele Episódio.
3. WHEN o usuário salva o formulário do Episódio sem preencher nenhum campo de Dados_Comerciais, THE Sistema SHALL persistir o Episódio com todos os campos comerciais como nulos e exibir o formulário do Episódio salvo.
4. IF o Episódio não possui status "Alta" e o Fisioterapeuta está autenticado, THEN THE Sistema SHALL permitir salvar alterações nos campos de Dados_Comerciais do Episódio.
5. WHEN o Episódio possui status "Alta", THE Sistema SHALL exibir os campos de Dados_Comerciais desabilitados para edição, impedindo qualquer alteração pelo Fisioterapeuta.
6. IF o usuário tenta salvar o formulário do Episódio com `session_value` preenchido com valor fora do intervalo de 0,01 a 999.999,99, THEN THE Sistema SHALL rejeitar o envio e exibir mensagem de erro indicando o intervalo válido sem persistir as alterações.
7. IF o usuário tenta salvar o formulário do Episódio com `contracted_procedure` excedendo 1000 caracteres, THEN THE Sistema SHALL rejeitar o envio e exibir mensagem de erro indicando o limite de caracteres sem persistir as alterações.
